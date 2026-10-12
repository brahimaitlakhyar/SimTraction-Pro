"""
Modèle cinématique et marche des trains (intégration temporelle pas à pas).
- Calcul des enveloppes rétrogrades de vitesse pour arrêts en gare et ralentissements
- Prise en compte du couplage avec la tension pantographe (U) et derating (kP)
- Régimes : traction, maintien de vitesse, marche sur l'erre (coasting), freinage, arrêt en gare (dwell).
"""

import math
import threading
from collections import OrderedDict
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from .noyaux import enveloppe_retrograde
from .train import Train
from .track import Parcours, DS

# Cache des parcours et enveloppes : les circulations d'un même engin, dans le même sens et avec
# les mêmes arrêts (grille répétée, situations N-1…) partagent ces tableaux, en lecture seule.
# Les clés utilisent l'identité des objets (tracé, engin) ; l'entrée garde une référence à ces
# objets et la vérifie, ce qui empêche toute confusion après réutilisation d'un id.
# Taille bornée en mémoire (LRU) et accès protégé (calculs simultanés de l'API).
_CACHE_OCTETS_MAX = 256 * 1024 * 1024
_cache: "OrderedDict[tuple, tuple]" = OrderedDict()
_cache_octets = 0
_cache_verrou = threading.Lock()


def _taille(valeur) -> int:
    if isinstance(valeur, Parcours):
        return valeur.vlim.nbytes + valeur.pente.nbytes + valeur.rayon.nbytes + valeur.tunnel.nbytes
    return sum(e.nbytes for e in valeur)


def _cache_lire(cle: tuple, refs: tuple):
    with _cache_verrou:
        entree = _cache.get(cle)
        if entree is not None and all(a is b for a, b in zip(entree[0], refs)):
            _cache.move_to_end(cle)
            return entree[1]
    return None


def _cache_ecrire(cle: tuple, refs: tuple, valeur):
    global _cache_octets
    taille = _taille(valeur)
    with _cache_verrou:
        ancien = _cache.pop(cle, None)
        if ancien is not None:
            _cache_octets -= ancien[2]
        _cache[cle] = (refs, valeur, taille)
        _cache_octets += taille
        while _cache_octets > _CACHE_OCTETS_MAX and len(_cache) > 1:
            _, (_, _, t) = _cache.popitem(last=False)
            _cache_octets -= t


class Marche:
    def __init__(self, troncons: List[Dict[str, Any]], train: Train, circ: Dict[str, Any], opts: Optional[Dict[str, Any]] = None):
        opts = opts or {}
        self.tr = train
        self.c = circ
        self.dt = float(opts.get("dt", 1.0) or 1.0)
        vmax = self.tr.v_max
        if opts.get("vitesse_ligne"):
            vmax = min(vmax, float(opts["vitesse_ligne"]))

        marge = float(opts.get("marge", 0.98) or 0.98)
        sens = int(circ.get("sens", 1))
        cle_p = ("parcours", id(troncons), sens, vmax, marge, train.longueur_m)
        self.p = _cache_lire(cle_p, (troncons,))
        if self.p is None:
            self.p = Parcours(troncons, sens, vmax, marge, train.longueur_m)
            _cache_ecrire(cle_p, (troncons,), self.p)

        gares_list = self.p.gares()
        self.arrets: List[Tuple[float, float, str]] = []  # [(s_m, duree_s, nom_gare)]
        arrets_dict = circ.get("arrets") or {}

        # Gares desservies (en excluant l'origine)
        for g in gares_list[1:]:
            duree = float(arrets_dict.get(g["nom"], 0.0) or 0.0)
            if duree > 0 and g["s"] > 1.0:
                self.arrets.append((g["s"], duree, g["nom"]))

        self.leg = 0
        cle_e = ("enveloppes", id(self.p), id(train), tuple(a[0] for a in self.arrets))
        self.env = _cache_lire(cle_e, (self.p, train))
        if self.env is None:
            self.env = self._enveloppes()
            _cache_ecrire(cle_e, (self.p, train), self.env)
        self.s = 0.0
        self.v = float(circ.get("v_initiale", 0.0) or 0.0) / 3.6  # m/s
        self.t = 0.0
        self.dwell = 0.0
        self.fini = False

    def bcap(self, v_ms: float) -> float:
        """Capacité de décélération de service maximale admissible (m/s²)."""
        v_kmh = v_ms * 3.6
        frein = (self.tr.effort_frein_elec(max(v_kmh, 1.0)) + self.tr.resistance(v_kmh)) / self.tr.masse_dyn_t
        return max(self.tr.decel_service or 0.0, frein, 0.05)

    def _enveloppes(self) -> List[np.ndarray]:
        """Calcul rétrograde des enveloppes maximales de vitesse (m/s) pour chaque arrêt."""
        n = self.p.n
        envs: List[np.ndarray] = []
        stops: List[Optional[float]] = [a[0] for a in self.arrets]
        stops.append(None)  # Terminus final

        for stop_s in stops:
            e = self.p.vlim / 3.6  # m/s
            if stop_s is not None:
                idx_stop = self.p.idx(stop_s)
                e[idx_stop:] = 0.0

            # Intégration rétrograde (noyau compilé, identique à la boucle sur self.bcap)
            tr = self.tr
            enveloppe_retrograde(e, DS, float(tr.decel_service or 0.0), tr.f_frein, tr.p_frein_kw,
                                 tr.davis_a, tr.davis_b, tr.davis_c, tr.masse_dyn_t)
            envs.append(e)

        return envs

    def env_at(self, s_m: float) -> float:
        """Vitesse de consigne (m/s) sur l'enveloppe active au point s."""
        e = self.env[self.leg]
        x_norm = s_m / DS
        i = int(x_norm)
        if i >= len(e) - 1:
            return float(e[-1])
        f = x_norm - i
        return float(e[i] * (1.0 - f) + e[i + 1] * f)

    def step(self, u_pantographe: Optional[float] = None, kp: float = 1.0) -> Dict[str, Any]:
        """Avance la marche d'un pas de temps dt."""
        tr = self.tr
        dt = self.dt
        u = u_pantographe if u_pantographe is not None else tr.u_nom

        idx_s = self.p.idx(self.s)
        pente = float(self.p.pente[idx_s])
        rayon = float(self.p.rayon[idx_s])
        tun = float(self.p.tunnel[idx_s])

        v = self.v
        v_kmh = v * 3.6
        self.t += dt

        # Arrêt en gare (dwell time)
        if self.dwell > 0:
            self.dwell -= dt
            return self._record(0.0, 0.0, u, "arret")

        # Résistances physiques
        if v > 0.01:
            fres = tr.resistance(v_kmh, tun) + tr.force_pente(pente) + tr.force_courbe(rayon)
        else:
            fres = max(0.0, tr.force_pente(pente))

        m = tr.masse_dyn_t
        v_obj = self.env_at(self.s + v * dt)
        stop = self.arrets[self.leg][0] if self.leg < len(self.arrets) else None

        # Gestion de l'arrêt précis en gare
        if stop is not None and (stop - self.s) < max(5.0, v * dt * 1.5) and v < 3.0:
            self.s = stop
            self.v = 0.0
            self.dwell = self.arrets[self.leg][1]
            self.leg += 1
            return self._record(-v / dt, 0.0, u, "freinage")

        # Calcul de l'effort commandé
        f_max = tr.effort_max(v_kmh, u, kp)
        a_need = (v_obj - v) / dt
        f_cmd = fres + m * a_need

        if f_cmd >= f_max:
            f = f_max
            regime = "traction"
        elif f_cmd >= 0:
            f = f_cmd
            regime = "maintien"
        elif a_need > -0.02:
            f = 0.0
            regime = "erre"
        else:
            f = max(f_cmd, fres - 1.5 * self.bcap(v) * m)
            regime = "freinage"

        a = (f - fres) / m
        v_next = v + a * dt
        if v_next < 0:
            v_next = 0.0
            a = -v / dt

        self.s += (v + v_next) / 2.0 * dt
        self.v = v_next

        if self.s >= self.p.longueur:
            self.s = self.p.longueur
            self.fini = True

        return self._record(a, f, u, regime)

    def _record(self, a: float, f: float, u: float, regime: str) -> Dict[str, Any]:
        """Génère l'enregistrement instantané."""
        v_kmh = self.v * 3.6
        if f > 0:
            p = self.tr.puissance_elec(f, v_kmh, u)
        else:
            p = self.tr.p_aux(u)
            if f < 0 and self.tr.rendement_recup > 0:
                p -= self.tr.rendement_recup * min(-f, self.tr.effort_frein_elec(v_kmh)) * v_kmh / 3.6

        dep_s = float(self.c.get("depart_s", 0.0) or 0.0)
        return {
            "t": dep_s + self.t,
            "s": self.s,
            "pk": self.p.pk(self.s),
            "v": v_kmh,
            "a": a,
            "f": f,
            "p_kw": p,
            "regime": regime,
        }


def marche_isolee(troncons: List[Dict[str, Any]], train: Train, circ: Dict[str, Any], opts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Calcule la marche isolée d'un train sous tension nominale constante."""
    m = Marche(troncons, train, circ, opts)
    out = []
    while not m.fini and m.t < 36000:
        out.append(m.step())
    return out
