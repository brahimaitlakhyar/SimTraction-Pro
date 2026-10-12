"""
Service d'importation et de compatibilité avec SimTraction V1.
Lit les fichiers CSV de BDD/ (séparateur point-virgule, encodage UTF-8 avec ou sans BOM).
"""

import os
import csv
from typing import List, Dict, Any, Optional

def parse_num(val: Any) -> Any:
    if val is None or val == "":
        return ""
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        n = float(s)
        return int(n) if n.is_integer() else n
    except ValueError:
        return str(val).strip()


def read_csv_semicolon(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    if not rows:
        return []
    headers = [h.strip() for h in rows[0]]
    result = []
    for r in rows[1:]:
        if not any(cell.strip() for cell in r):
            continue
        row_dict = {}
        for idx, h in enumerate(headers):
            val = r[idx].strip() if idx < len(r) else ""
            row_dict[h] = val
        result.append(row_dict)
    return result


def parse_v1_trace(filepath: str) -> List[Dict[str, Any]]:
    rows = read_csv_semicolon(filepath)
    out = []
    for r in rows:
        out.append({
            "pk_ini": parse_num(r.get("PK début (km)", 0)),
            "pk_fin": parse_num(r.get("PK fin (km)", 0)),
            "pente": parse_num(r.get("Déclivité (‰)", 0)),
            "rayon": parse_num(r.get("Rayon (m, 0 = alignement)", 0)),
            "limite": parse_num(r.get("Limite (km/h, 0 = aucune)", 0)),
            "gare": r.get("Gare", "").strip(),
            "tunnel": parse_num(r.get("Majoration tunnel (ex. 0,2)", 0)),
        })
    return out


def parse_v1_materiel(filepath: str) -> List[Dict[str, Any]]:
    rows = read_csv_semicolon(filepath)
    out = []
    for r in rows:
        out.append({
            "ref": parse_num(r.get("Réf.", 0)),
            "nom": r.get("Désignation", "").strip(),
            "type": r.get("Modèle de traction (serie_cc / tabule)", "tabule").strip(),
            "masse_t": parse_num(r.get("Masse (t)", 100)),
            "masse_dyn_t": parse_num(r.get("Masse dynamique (t)", 0)),
            "longueur_m": parse_num(r.get("Longueur (m)", 0)),
            "f_max": parse_num(r.get("Effort max (kN)", 200)),
            "v1": parse_num(r.get("v1 (km/h, moteur série)", 0)),
            "v_max": parse_num(r.get("Vmax (km/h)", 160)),
            "p_max_kw": parse_num(r.get("P max jante (kW)", 4000)),
            "rendement": parse_num(r.get("Rendement", 0.85)),
            "p_aux_kw": parse_num(r.get("Auxiliaires (kW)", 0)),
            "cos_phi": parse_num(r.get("cos φ", 0.98)),
            "u_nom": parse_num(r.get("U nominale (V)", 3000)),
            "davis_a": parse_num(r.get("Davis A (kN)", 2)),
            "davis_b": parse_num(r.get("Davis B (kN/(km/h))", 0.02)),
            "davis_c": parse_num(r.get("Davis C (kN/(km/h)²)", 0.0004)),
            "coef_courbe": parse_num(r.get("Coef. courbe (kN·m)", 0)),
            "c2_ohm": parse_num(r.get("c2 (Ω)", 0)),
            "c3": parse_num(r.get("c3 (kN/A²)", 0)),
            "i_aux": parse_num(r.get("I aux (A)", 0)),
            "f_frein": parse_num(r.get("Frein élec. (kN)", 100)),
            "p_frein_kw": parse_num(r.get("P frein élec. (kW)", 2000)),
            "rendement_recup": parse_num(r.get("Récupération (0–1)", 0)),
            "decel_service": parse_num(r.get("Décél. service (m/s²)", 0.2)),
        })
    return out


def parse_v1_trafic(filepath: str) -> List[Dict[str, Any]]:
    rows = read_csv_semicolon(filepath)
    out = []
    for r in rows:
        out.append({
            "ref_train": parse_num(r.get("Train (réf.)", 0)),
            "sens": parse_num(r.get("Sens (1 ou 2)", 1)),
            "depart": r.get("Départ (hh:mm:ss)", "00:00:00").strip(),
            "voie": parse_num(r.get("Voie", 1)),
            "v_initiale": parse_num(r.get("Vitesse initiale (km/h)", 0)),
            "arrets": r.get("Arrêts (Gare:durée s ; …)", "").strip(),
            "libelle": r.get("Libellé", "").strip(),
        })
    return out


def parse_v1_sst(filepath: str) -> List[Dict[str, Any]]:
    rows = read_csv_semicolon(filepath)
    out = []
    for r in rows:
        out.append({
            "nom": r.get("Nom", "SST").strip(),
            "pk": parse_num(r.get("PK (km)", 0)),
            "en_service": r.get("En service (oui/non)", "oui").strip(),
            "u0": parse_num(r.get("U0 à vide (V)", 3600)),
            "r_int": parse_num(r.get("R interne (Ω) – 3 kV", 0.05)),
            "p_nom_kw": parse_num(r.get("P nominale (kW) – 3 kV", 0)),
            "s_nom_mva": parse_num(r.get("S transfo (MVA) – 25 kV", 20)),
            "ucc_pct": parse_num(r.get("ucc (%) – 25 kV", 10)),
            "scc_mva": parse_num(r.get("Scc réseau HT (MVA) – 25 kV", 2000)),
        })
    return out


def parse_v1_postes(filepath: str) -> List[Dict[str, Any]]:
    rows = read_csv_semicolon(filepath)
    out = []
    for r in rows:
        out.append({
            "nom": r.get("Nom", "Poste").strip(),
            "pk": parse_num(r.get("PK (km)", 0)),
            "type": r.get("Type (PS, SP, SSP, ATS)", "PS").strip(),
            "at": r.get("Autotransformateur (oui/non)", "non").strip(),
        })
    return out


def parse_v1_sites(filepath: str) -> List[Dict[str, Any]]:
    rows = read_csv_semicolon(filepath)
    out = []
    for r in rows:
        out.append({
            "nom": r.get("Site", "").strip(),
            "pk": parse_num(r.get("PK (km)", 0)),
            "scc_mva": parse_num(r.get("Scc réseau HT (MVA)", 2000)),
        })
    return out


def parse_v1_params(filepath: str) -> Dict[str, Any]:
    rows = read_csv_semicolon(filepath)
    res: Dict[str, Any] = {}
    for r in rows:
        code = r.get("Code", "").strip()
        val = r.get("Valeur", "").strip()
        if not code:
            continue
        parsed_v = parse_num(val)
        keys = code.split(".")
        d = res
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = parsed_v
    return res


def charger_projet_v1(dossier_projet: str) -> Dict[str, Any]:
    """Charge l'ensemble des 7 fichiers d'un projet SimTraction V1."""
    params_file = os.path.join(dossier_projet, "parametres.csv")
    trace_file = os.path.join(dossier_projet, "trace.csv")
    materiel_file = os.path.join(dossier_projet, "materiel.csv")
    trafic_file = os.path.join(dossier_projet, "trafic.csv")
    sst_file = os.path.join(dossier_projet, "sous_stations.csv")
    postes_file = os.path.join(dossier_projet, "postes.csv")
    sites_file = os.path.join(dossier_projet, "sites.csv")

    params = parse_v1_params(params_file)
    project_id = os.path.basename(os.path.normpath(dossier_projet))
    params["id"] = project_id
    if not params.get("nom"):
        params["nom"] = project_id.replace("_", " ")

    params["trace"] = params.get("trace", {})
    params["trace"]["troncons"] = parse_v1_trace(trace_file)
    params["trains"] = parse_v1_materiel(materiel_file)
    params["trafic"] = parse_v1_trafic(trafic_file)

    params["alimentation"] = params.get("alimentation", {})
    params["alimentation"]["sst"] = parse_v1_sst(sst_file)
    params["alimentation"]["postes"] = parse_v1_postes(postes_file)

    params["dimensionnement"] = params.get("dimensionnement", {})
    params["dimensionnement"]["candidats"] = parse_v1_sites(sites_file)

    return params
