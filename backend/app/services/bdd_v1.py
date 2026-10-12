"""
Accès en lecture à la base de données SimTraction V1 (dossier BDD/ en CSV).
Source des projets et bibliothèques tant que la persistance PostgreSQL n'est pas en place.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.import_v1 import charger_projet_v1, parse_v1_materiel, read_csv_semicolon, parse_num


class ProjetIntrouvable(LookupError):
    pass


def _bdd() -> Path:
    return Path(get_settings().v1_bdd_dir)


def _dossier_projet(project_id: str) -> Path:
    """Dossier d'un projet ; refuse tout identifiant qui sortirait de BDD/projets."""
    racine = (_bdd() / "projets").resolve()
    dossier = (racine / project_id).resolve()
    if dossier.parent != racine or not (dossier / "parametres.csv").is_file():
        raise ProjetIntrouvable(project_id)
    return dossier


def resume_projet(P: Dict[str, Any]) -> Dict[str, Any]:
    """Résumé d'un projet pour les listes (équivalent de B.resume en V1)."""
    longueur = sum(max(0.0, float(t["pk_fin"]) - float(t["pk_ini"]))
                   for t in P["trace"]["troncons"] if t["pk_ini"] != "" and t["pk_fin"] != "")
    alim = P.get("alimentation") or {}
    return {
        "id": P["id"],
        "nom": P.get("nom") or P["id"],
        "systeme": P.get("systeme") or "cc3000",
        "reference": P.get("reference") or "",
        "description": P.get("description") or "",
        "modifie": P.get("modifie") or "",
        "longueur_km": round(longueur, 3),
        "duree_s": P.get("duree_s") or 3600,
        "nb_trains": len(P.get("trains") or []),
        "nb_circulations": len(P.get("trafic") or []),
        "nb_sst": len(alim.get("sst") or []),
        "nb_postes": len(alim.get("postes") or []),
    }


def lister_projets() -> List[Dict[str, Any]]:
    racine = _bdd() / "projets"
    if not racine.is_dir():
        return []
    out = []
    for d in sorted(racine.iterdir()):
        if (d / "parametres.csv").is_file():
            out.append(resume_projet(charger_projet_v1(str(d))))
    return out


def charger_projet(project_id: str) -> Dict[str, Any]:
    return charger_projet_v1(str(_dossier_projet(project_id)))


def projet_pour_calcul(project_id: str) -> Dict[str, Any]:
    """
    Projet prêt pour le moteur : seuils de normes.csv, surchargés par les seuils propres
    au projet (même priorité que V1 : défauts moteur < normes.csv < projet).
    """
    P = charger_projet(project_id)
    famille = "cc3000" if P.get("systeme") == "cc3000" else "ac25"
    base = {n["code"]: n["valeur"] for n in lister_normes(famille) if n["valeur"] != ""}
    propres = {k: v for k, v in (P.get("normes") or {}).items() if v not in ("", None)}
    P["normes"] = {**base, **propres}
    return P


def lister_materiel() -> List[Dict[str, Any]]:
    """Bibliothèque commune du matériel roulant (BDD/materiel.csv)."""
    return parse_v1_materiel(str(_bdd() / "materiel.csv"))


def lister_sites_ht() -> List[Dict[str, Any]]:
    """Postes HT de raccordement possibles (BDD/sites_ht.csv)."""
    return [
        {
            "ligne": r.get("Ligne", ""),
            "nom": r.get("Site", ""),
            "pk": parse_num(r.get("PK (km)", "")),
            "scc_mva": parse_num(r.get("Scc réseau HT (MVA)", "")),
            "tension_kv": parse_num(r.get("Tension HT (kV)", "")),
            "remarque": r.get("Remarque", ""),
        }
        for r in read_csv_semicolon(str(_bdd() / "sites_ht.csv"))
    ]


def _parse_num_v1(v: Any) -> Any:
    """parseNum de V1 : nombre si la valeur en est un (virgule décimale admise), sinon texte inchangé."""
    if v in ("", None):
        return ""
    s = "".join(str(v).split()).replace(",", ".", 1)
    try:
        n = float(s)
    except ValueError:
        return v
    if s == "" or n != n or n in (float("inf"), float("-inf")):
        return v
    return int(n) if n.is_integer() else n


def lire_reglages() -> Dict[str, Any]:
    """Réglages par défaut (BDD/parametres/reglages.csv) : code → valeur."""
    rows = read_csv_semicolon(str(_bdd() / "parametres" / "reglages.csv"))
    return {r["Code"].strip(): _parse_num_v1(r.get("Valeur", "")) for r in rows if r.get("Code", "").strip()}


def lister_normes(systeme: Optional[str] = None) -> List[Dict[str, Any]]:
    """Seuils normatifs par défaut (BDD/parametres/normes.csv)."""
    rows = read_csv_semicolon(str(_bdd() / "parametres" / "normes.csv"))
    out = [
        {
            "systeme": r.get("Système (cc3000 / ac25)", ""),
            "code": r.get("Code", ""),
            "libelle": r.get("Paramètre", ""),
            "valeur": parse_num(r.get("Valeur", "")),
            "reference": r.get("Référence", ""),
        }
        for r in rows
    ]
    return [n for n in out if not systeme or n["systeme"] == systeme]
