"""
Gestion du tracé ferroviaire, profil en long et discrétisation spatiale.
- Coord : projection biunivoque entre Points Kilométriques (PK) et abscisse curviligne continue x (km)
- Parcours : discrétisation fine au pas de DS = 2.0 m avec déclivités, courbures, tunnels et limitations de vitesse
  avec prise en compte du dégagement de la queue du train.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from .noyaux import minimum_glissant

DS = 2.0  # Pas spatial en mètres


class Coord:
    """Gestion des discontinuités et sauts de PK en coordonnée continue x (km)."""

    def __init__(self, troncons: List[Dict[str, Any]]):
        self.t = [[float(t["pk_ini"]), float(t["pk_fin"])] for t in troncons if float(t["pk_fin"]) > float(t["pk_ini"])]
        if not self.t:
            raise ValueError("Le tracé doit contenir au moins un tronçon valide.")
        self.cum = []
        c = 0.0
        for seg in self.t:
            self.cum.append(c)
            c += seg[1] - seg[0]
        self.total = c

    def x(self, pk: float) -> float:
        """Convertit un PK en abscisse continue x (km)."""
        t = self.t
        if pk <= t[0][0]:
            return pk - t[0][0]
        lo = 0
        hi = len(t) - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            if t[mid][1] < pk:
                lo = mid + 1
            else:
                hi = mid
        if pk > t[-1][1]:
            return self.total + pk - t[-1][1]
        return self.cum[lo] + max(pk - t[lo][0], 0.0)

    def pk(self, x_val: float) -> float:
        """Convertit une abscisse continue x (km) en PK réel."""
        if x_val <= 0.0:
            return self.t[0][0] + x_val
        for i, seg in enumerate(self.t):
            seg_len = seg[1] - seg[0]
            if x_val <= self.cum[i] + seg_len:
                return seg[0] + (x_val - self.cum[i])
        return self.t[-1][1] + (x_val - self.total)


def extract_gares(troncons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extrait la liste ordonnée des gares du tracé avec leurs PK de début et de fin."""
    out = []
    for t in troncons:
        gare = (t.get("gare") or "").strip()
        if gare and (not out or out[-1]["nom"] != gare):
            out.append({
                "nom": gare,
                "pk": float(t["pk_ini"]),
                "pk_fin": float(t["pk_fin"])
            })
    return out


class Parcours:
    """Parcours spatial échantillonné d'une circulation dans son sens de marche."""

    def __init__(self, troncons: List[Dict[str, Any]], sens: int, v_max: float, marge: float = 0.98, longueur_m: float = 0.0):
        # sens > 0 : sens 1 (PK croissants) ; sens < 0 : sens 2 (PK décroissants)
        trs = list(troncons) if sens > 0 else list(reversed(troncons))
        self.sens = 1 if sens > 0 else -1
        self.b: List[Tuple[float, float, Dict[str, Any]]] = []
        s_cum = 0.0
        for seg in trs:
            seg_len_m = (float(seg["pk_fin"]) - float(seg["pk_ini"])) * 1000.0
            if seg_len_m <= 0.0:
                continue
            self.b.append((s_cum, s_cum + seg_len_m, seg))
            s_cum += seg_len_m

        self.longueur = s_cum
        n = int(np.ceil(s_cum / DS)) + 1
        self.n = n

        # Échantillonnage vectorisé : tronçon de chaque point i·DS (équivalent de l'avance
        # « while x >= fin du tronçon j : j += 1 »), puis valeurs du tronçon.
        fins = np.array([b[1] for b in self.b], dtype=np.float64)
        x = np.arange(n, dtype=np.float64) * DS
        j = np.minimum(np.searchsorted(fins, x, side="right"), len(self.b) - 1)

        segs = [b[2] for b in self.b]
        lim_seg = [float(t.get("limite") or 0.0) for t in segs]
        vl_seg = np.array([(min(v_max, lim) if lim > 0 else v_max) * marge for lim in lim_seg], dtype=np.float64)
        pente_seg = np.array([float(t.get("pente") or 0.0) * self.sens for t in segs], dtype=np.float64)
        rayon_seg = np.array([float(t.get("rayon") or 0.0) for t in segs], dtype=np.float64)
        tunnel_seg = np.array([float(t.get("tunnel") or 0.0) for t in segs], dtype=np.float64)

        vl = vl_seg[j]
        self.pente = pente_seg[j].astype(np.float32)
        self.rayon = rayon_seg[j].astype(np.float32)
        self.tunnel = tunnel_seg[j].astype(np.float32)

        # Dégagement de la queue du train : minimum glissant sur la longueur du train
        k = int(round(longueur_m / DS))
        if k > 0:
            vl = minimum_glissant(vl, k)

        self.vlim = vl

    def idx(self, s_m: float) -> int:
        """Indice spatial correspondant à la distance s en mètres."""
        return min(max(int(s_m / DS), 0), self.n - 1)

    def pk(self, s_m: float) -> float:
        """Convertit une distance s (m) parcourue depuis l'origine en PK de la ligne."""
        s_m = min(max(s_m, 0.0), self.longueur)
        lo = 0
        hi = len(self.b) - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            if self.b[mid][1] < s_m:
                lo = mid + 1
            else:
                hi = mid
        seg = self.b[lo][2]
        fraction_km = (s_m - self.b[lo][0]) / 1000.0
        if self.sens > 0:
            return float(seg["pk_ini"]) + fraction_km
        return float(seg["pk_fin"]) - fraction_km

    def gares(self) -> List[Dict[str, Any]]:
        """Gares rencontrées dans l'ordre de parcours."""
        out = []
        for s_ini, _, seg in self.b:
            gare = (seg.get("gare") or "").strip()
            if gare and (not out or out[-1]["nom"] != gare):
                out.append({"nom": gare, "s": s_ini})
        return out
