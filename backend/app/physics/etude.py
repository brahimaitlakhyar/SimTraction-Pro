"""
Étude complète d'un projet : situation normale, situations dégradées N-1 et séries allégées
pour l'interface. Équivalent Python de la commande « simuler » du worker de SimTraction V1.
"""

import math
import time
from typing import Any, Callable, Dict, List, Optional

from .simulation import (
    SimulationEnv,
    analyser,
    build_configuration_n1,
    build_network_configuration,
    calculer_profils_isoles,
    simuler,
    verifications_normatives,
)

Progression = Callable[[float, str], None]


def _alleger(valeurs, pas: int, decimales: int = 3) -> List[float]:
    """Sous-échantillonne une série (un point sur `pas`) et arrondit."""
    return [round(float(valeurs[i]), decimales) for i in range(0, len(valeurs), pas)]


def series_interface(R: Dict[str, Any], env: SimulationEnv) -> Dict[str, Any]:
    """Séries allégées pour les graphiques : par circulation (pas ≈ 5 s) et par SST (pas ≈ 10 s)."""
    dt = float(R["dt"])
    st = max(1, round(5.0 / dt))
    st2 = max(1, round(10.0 / dt))
    ac = R["famille"] != "cc3000"
    ns, nt = int(R["ns"]), int(R["nt"])

    circ = [
        {
            "nom": c["nom"],
            "train": env.trains[c["ref"]].nom,
            "t": _alleger(c["t"], st),
            "pk": _alleger(c["pk"], st),
            "u": _alleger(c["u"], st),
            "v": _alleger(c["v"], st),
        }
        for c in R["circ"] if c["t"]
    ]
    t_sst = [(it + 1) * dt for it in range(0, nt, st2)]
    p_src = R["sst_s"] if ac else R["sst_p"]
    sst = [
        {"nom": s["nom"], "p": [round(float(p_src[it * ns + j])) for it in range(0, nt, st2)]}
        for j, s in enumerate(R["cfg"]["sst"])
    ]
    return {"circ": circ, "t_sst": t_sst, "sst": sst}


def executer_etude(
    env: SimulationEnv,
    opts: Optional[Dict[str, Any]] = None,
    progression: Optional[Progression] = None,
) -> Dict[str, Any]:
    """
    opts : dt (s), couplage (bool), n1 (True / False / "interm").
    Retourne { A, conf, n1, series, avert, opts, duree } comme le worker V1.
    """
    o = {"dt": 1.0, "couplage": True, "n1": True, **(opts or {})}
    t0 = time.time()

    def prog(f: float, txt: str):
        if progression:
            progression(f, txt)

    if not (env.P.get("alimentation") or {}).get("sst"):
        raise ValueError("Aucune sous-station dans le projet : lancez d'abord le dimensionnement "
                         "ou saisissez les sous-stations existantes.")
    if not env.circ:
        raise ValueError("Aucune circulation : complétez la grille horaire.")

    cfg = build_network_configuration(env)
    actives = [s for s in cfg["sst"] if s.get("actif")]
    part = 0.5 if o["n1"] else 1.0

    R = simuler(env, {"cfg": cfg, "couplage": o["couplage"], "dt": o["dt"]},
                lambda f, _txt: prog(f * part, "Situation normale…"))
    A = analyser(env, R)
    conf = verifications_normatives(A, "normale")

    n1: List[Dict[str, Any]] = []
    if o["n1"] and len(actives) > 1:
        dt1 = max(float(o["dt"]), 2.0)
        profils = calculer_profils_isoles(env, dt1)
        pk_act = [s["pk"] for s in actives]
        pk_g, pk_d = min(pk_act), max(pk_act)
        k0 = 0
        for k, s in enumerate(cfg["sst"]):
            if not s.get("actif"):
                continue
            if o["n1"] == "interm" and len(actives) > 2 and s["pk"] in (pk_g, pk_d):
                continue
            prog(0.5 + 0.5 * min(1.0, k0 / len(actives)), f"Situation N-1 : {s['nom']} hors service…")
            k0 += 1
            R1 = simuler(env, {"cfg": build_configuration_n1(env, k), "profils": profils, "dt": dt1})
            A1 = analyser(env, R1)
            charge_max, charge_nom = 0.0, ""
            for x in A1["sst"]:
                if x["actif"] and x["charge"] > charge_max:
                    charge_max, charge_nom = x["charge"], x["nom"]
            pire = A1["glob"]["pire"]
            n1.append({
                "nom": f"N-1 {s['nom']}",
                "k": k,
                "u_min": A1["glob"]["u_min"],
                "pk_u_min": pire["pk_u_min"] if pire else None,
                "u_moy_zone_min": A1["glob"]["u_moy_zone_min"],
                "charge_max": charge_max,
                "charge_max_nom": charge_nom,
                "charges": [x["charge"] for x in A1["sst"]],
                "conf": verifications_normatives(A1, "N-1"),
            })

    prog(1.0, "Terminé")
    return {
        "A": A,
        "conf": conf,
        "n1": n1,
        "series": series_interface(R, env),
        "avert": list(env.avert),
        "opts": o,
        "duree": time.time() - t0,
    }


def json_sur(x: Any) -> Any:
    """Convertit récursivement en types JSON (NaN / ±inf → None, numpy → float / list)."""
    if isinstance(x, dict):
        return {str(k): json_sur(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_sur(v) for v in x]
    if hasattr(x, "tolist"):
        return json_sur(x.tolist())
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    return x
