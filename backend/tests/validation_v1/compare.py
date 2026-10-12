"""
Validation de non-régression du moteur Python face au moteur JavaScript de SimTraction V1.

Le moteur V1 (SimTraction_V1/SimTraction.html) est exécuté sous Node par v1_run.js, qui écrit
le projet tel que lu par V1, les grandeurs d'analyse et les séries temporelles. Ce module
relance le moteur Python sur le même projet et compare toutes les grandeurs.

Usage en ligne de commande (depuis backend/) :
    python -m tests.validation_v1.compare <projet> [dt]
"""

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.physics.simulation import SimulationEnv, simuler, analyser
from app.services.import_v1 import charger_projet_v1

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.abspath(os.path.join(ICI, "..", "..", ".."))
DOSSIER_V1 = os.path.join(RACINE, "SimTraction_V1")
TOLERANCE = 5e-4  # 0,05 % (plan de réalisation, phase 2)

Ecart = Tuple[float, str, Any, Any]


def executer_v1(projet: str, dt: float, sortie: str) -> Dict[str, Any]:
    """Lance le moteur V1 sous Node et retourne ses résultats."""
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js introuvable : nécessaire pour exécuter le moteur V1.")
    subprocess.run([node, os.path.join(ICI, "v1_run.js"), DOSSIER_V1, projet, str(dt), sortie],
                   check=True, capture_output=True, text=True, encoding="utf-8")
    with open(sortie, encoding="utf-8") as f:
        return json.load(f)


def _num(x: Any) -> Any:
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return x
    return x


def _ecart(a: Any, b: Any) -> float:
    a, b = _num(a), _num(b)
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return 0.0 if a == b else math.inf
    if math.isnan(a) and math.isnan(b):
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


def _ecart_serie(nom: str, a: np.ndarray, b: np.ndarray, ref: float, t: List[float]) -> Ecart:
    i = int(np.argmax(np.abs(a - b)))
    return (abs(a[i] - b[i]) / max(ref, 1.0), f"{nom}[t={t[i]:.0f}]", float(a[i]), float(b[i]))


def comparer(V: Dict[str, Any], env: SimulationEnv, R: Dict[str, Any], A: Dict[str, Any]) -> List[Ecart]:
    """Liste (écart relatif, grandeur, V1, Python) triée du plus grand au plus petit écart."""
    out: List[Ecart] = []

    def chk(nom: str, a: Any, b: Any):
        out.append((_ecart(a, b), nom, a, b))

    gV, gP = V["A"]["glob"], A["glob"]
    for k in ["u_min", "energie_sst_kwh", "energie_trains_kwh", "recup_kwh", "pertes_ligne_kwh",
              "pertes_sst_kwh", "rheostat_kwh", "rendement", "v_rail_max", "u_moy_zone_min", "nb_circ"]:
        chk(f"glob.{k}", gV[k], gP[k])
    chk("nb_circulations", V["nb_circ"], len(env.circ))

    for j, (sv, sp) in enumerate(zip(V["A"]["sst"], A["sst"])):
        for k in ["energie_kwh", "p_max", "i_max", "p_1min", "p_15min", "p_1h", "s_1min", "s_10min",
                  "s_1h", "i_eff_15min", "u_min", "charge"]:
            if k in sv and k in sp:
                chk(f"sst[{j}].{k}", sv[k], sp[k])
    for tv, tp in zip(V["A"]["trains"], A["trains"]):
        for k in ["duree_s", "energie_kwh", "recup_kwh", "u_min", "pk_u_min", "u_moy_utile",
                  "t_sous_umin1", "v_rail_max"]:
            chk(f"train[{tv['id']}].{k}", tv[k], tp[k])
    for z, (zv, zp) in enumerate(zip(V["A"]["zones"], A["zones"])):
        for k in ["u_moy_utile", "u_min", "n"]:
            chk(f"zone[{z}].{k}", zv[k], zp[k])

    # Séries temporelles, rapportées à une grandeur de référence de chaque série
    un = float(V["normes"]["un"])
    for cv, cp in zip(V["R"]["circ"], R["circ"]):
        if len(cv["t"]) != len(cp["t"]):
            out.append((math.inf, f"circ[{cv['id']}].nb_pas", len(cv["t"]), len(cp["t"])))
        n = min(len(cv["t"]), len(cp["t"]))
        if not n:
            continue
        for k in ["u", "v", "pk", "p"]:
            a, b = np.array(cv[k][:n], float), np.array(cp[k][:n], float)
            ref = {"u": un, "v": np.abs(a).max(), "pk": a.max() - a.min(), "p": np.abs(a).max()}[k]
            out.append(_ecart_serie(f"circ[{cv['id']}].{k}", a, b, ref, cv["t"]))
    a, b = np.array(V["R"]["sst_p"], float), np.array(R["sst_p"], float)
    i = int(np.argmax(np.abs(a - b)))
    out.append((abs(a[i] - b[i]) / max(np.abs(a).max(), 1.0), f"sst_p[{i}]", float(a[i]), float(b[i])))

    out.sort(key=lambda e: -e[0])
    return out


def valider(projet: str, dt: float = 5.0, depuis_csv: bool = True, v1: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[Ecart]]:
    """
    Exécute V1 et Python sur un projet et retourne (résultats V1, écarts).
    depuis_csv=True : chaîne complète Python (import_v1 + moteur) ;
    depuis_csv=False : moteur Python seul, sur le projet tel que lu par V1.
    """
    if v1 is None:
        with tempfile.TemporaryDirectory() as tmp:
            v1 = executer_v1(projet, dt, os.path.join(tmp, "v1.json"))
    data = charger_projet_v1(os.path.join(DOSSIER_V1, "BDD", "projets", projet)) if depuis_csv else dict(v1["projet"])
    env = SimulationEnv(data)
    R = simuler(env, {"dt": dt, "couplage": True})
    A = analyser(env, R)
    return v1, comparer(v1, env, R, A)


def comparer_etude(V: Dict[str, Any], P: Dict[str, Any]) -> List[Ecart]:
    """Compare l'étude complète (normale + N-1 + séries allégées) : V = worker V1, P = executer_etude."""
    out: List[Ecart] = []

    def chk(nom: str, a: Any, b: Any):
        out.append((_ecart(a, b), nom, a, b))

    chk("glob.u_min", V["A"]["glob"]["u_min"], P["A"]["glob"]["u_min"])
    chk("conf.nb", len(V["conf"]), len(P["conf"]))
    for i, (cv, cp) in enumerate(zip(V["conf"], P["conf"])):
        chk(f"conf[{i}].valeur", cv["valeur"], cp["valeur"])
        chk(f"conf[{i}].ok", cv["ok"], cp["ok"])

    chk("n1.nb", len(V["n1"]), len(P["n1"]))
    for nv, np_ in zip(V["n1"], P["n1"]):
        for k in ["nom", "k", "u_min", "pk_u_min", "u_moy_zone_min", "charge_max", "charge_max_nom"]:
            chk(f"{nv['nom']}.{k}", nv[k], np_[k])
        for j, (a, b) in enumerate(zip(nv["charges"], np_["charges"])):
            chk(f"{nv['nom']}.charges[{j}]", a, b)
        for i, (cv, cp) in enumerate(zip(nv["conf"], np_["conf"])):
            chk(f"{nv['nom']}.conf[{i}].ok", cv["ok"], cp["ok"])

    sv, sp = V["series"], P["series"]
    chk("series.nb_circ", len(sv["circ"]), len(sp["circ"]))
    chk("series.t_sst", len(sv["t_sst"]), len(sp["t_sst"]))
    for cv, cp in zip(sv["circ"], sp["circ"]):
        for k in ["t", "pk", "u", "v"]:
            chk(f"series.{cv['nom']}.{k}.n", len(cv[k]), len(cp[k]))
            if cv[k]:
                a, b = np.array(cv[k], float), np.array(cp[k][:len(cv[k])], float)
                out.append(_ecart_serie(f"series.{cv['nom']}.{k}", a, b, max(np.abs(a).max(), 1.0), cv["t"]))
    for s1, s2 in zip(sv["sst"], sp["sst"]):
        a, b = np.array(s1["p"], float), np.array(s2["p"][:len(s1["p"])], float)
        out.append((float(np.abs(a - b).max() / max(np.abs(a).max(), 1.0)) if len(a) else 0.0, f"series.sst.{s1['nom']}", None, None))

    out.sort(key=lambda e: -e[0])
    return out


def valider_etude(projet: str, dt: float = 5.0) -> List[Ecart]:
    """Exécute l'étude complète (worker V1 sous Node / executer_etude Python) et compare."""
    from app.physics.etude import executer_etude

    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js introuvable : nécessaire pour exécuter le moteur V1.")
    with tempfile.TemporaryDirectory() as tmp:
        sortie = os.path.join(tmp, "v1.json")
        subprocess.run([node, os.path.join(ICI, "v1_run.js"), DOSSIER_V1, projet, str(dt), sortie, "etude"],
                       check=True, capture_output=True, text=True, encoding="utf-8")
        with open(sortie, encoding="utf-8") as f:
            V = json.load(f)["etude"]
    env = SimulationEnv(charger_projet_v1(os.path.join(DOSSIER_V1, "BDD", "projets", projet)))
    return comparer_etude(V, executer_etude(env, {"dt": dt, "couplage": True, "n1": True}))


def main():
    projet = sys.argv[1]
    dt = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    v1 = None
    for depuis_csv, titre in [(False, "Moteur seul (projet lu par le parseur V1)"),
                              (True, "Chaîne complète (import_v1 + moteur)")]:
        v1, ecarts = valider(projet, dt, depuis_csv, v1)
        ko = [e for e in ecarts if e[0] > TOLERANCE]
        print(f"\n=== {projet} dt={dt:g}s – {titre} ===")
        print(f"{len(ecarts)} grandeurs, {len(ko)} au-delà de 0,05 % ; écart max {ecarts[0][0] * 100:.3g} %")
        for e, nom, a, b in ecarts[:10]:
            print(f"  {'KO' if e > TOLERANCE else 'ok'} {e * 100:10.3g} %  {nom:36s} V1={a}  Py={b}")

    ecarts = valider_etude(projet, dt)
    ko = [e for e in ecarts if e[0] > TOLERANCE]
    print(f"\n=== {projet} dt={dt:g}s – Étude complète (normale + N-1 + séries) ===")
    print(f"{len(ecarts)} grandeurs, {len(ko)} au-delà de 0,05 % ; écart max {ecarts[0][0] * 100:.3g} %")
    for e, nom, a, b in ecarts[:10]:
        print(f"  {'KO' if e > TOLERANCE else 'ok'} {e * 100:10.3g} %  {nom:36s} V1={a}  Py={b}")


if __name__ == "__main__":
    main()
