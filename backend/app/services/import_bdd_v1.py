"""
Import de la base SimTraction V1 (dossier BDD/ en CSV) dans la base de données.

    python -m app.services.import_bdd_v1 [dossier_BDD] [--remplacer]

Sans --remplacer, les projets déjà présents (même identifiant) sont conservés.
Les bibliothèques (matériel, sites HT, normes, réglages) sont remplacées.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import delete

from app.core.config import get_settings
from app.db import session
from app.db.models import CHAMPS_MATERIEL, CHAMPS_SITES_HT, MaterielBibliotheque, Norme, Projet, Reglage, SiteHT
from app.services.import_v1 import charger_projet_v1, parse_num, parse_v1_materiel, read_csv_semicolon
from app.services.projets import _dict_vers_ligne, ecrire_projet_complet


def _num(v: Any):
    n = parse_num(v)
    return None if n == "" or isinstance(n, str) else float(n)


def importer_bibliotheques(s, bdd: Path) -> Dict[str, int]:
    s.execute(delete(MaterielBibliotheque))
    s.execute(delete(SiteHT))
    s.execute(delete(Norme))
    s.execute(delete(Reglage))

    materiel = parse_v1_materiel(str(bdd / "materiel.csv"))
    for i, m in enumerate(materiel):
        s.add(_dict_vers_ligne(MaterielBibliotheque, m, CHAMPS_MATERIEL, i))

    sites = read_csv_semicolon(str(bdd / "sites_ht.csv"))
    for i, r in enumerate(sites):
        d = {"ligne": r.get("Ligne", ""), "nom": r.get("Site", ""), "pk": r.get("PK (km)", ""),
             "scc_mva": r.get("Scc réseau HT (MVA)", ""), "tension_kv": r.get("Tension HT (kV)", ""),
             "remarque": r.get("Remarque", "")}
        s.add(_dict_vers_ligne(SiteHT, d, CHAMPS_SITES_HT, i))

    normes = read_csv_semicolon(str(bdd / "parametres" / "normes.csv"))
    for i, r in enumerate(normes):
        s.add(Norme(ordre=i, systeme=r.get("Système (cc3000 / ac25)", "").strip(), code=r.get("Code", "").strip(),
                    libelle=r.get("Paramètre", ""), valeur=_num(r.get("Valeur", "")), reference=r.get("Référence", "")))

    reglages = [r for r in read_csv_semicolon(str(bdd / "parametres" / "reglages.csv")) if r.get("Code", "").strip()]
    for i, r in enumerate(reglages):  # valeur brute conservée (« 3000/6000 », « 0,98 ») comme dans le CSV
        s.add(Reglage(ordre=i, code=r["Code"].strip(), libelle=r.get("Paramètre", ""), valeur=r.get("Valeur", "").strip()))

    return {"materiel": len(materiel), "sites_ht": len(sites), "normes": len(normes), "reglages": len(reglages)}


def importer_bdd_v1(bdd: Path, remplacer: bool = False) -> Dict[str, Any]:
    bdd = Path(bdd)
    if not (bdd / "projets").is_dir():
        raise FileNotFoundError(f"Dossier BDD V1 introuvable : {bdd}")
    importes: List[str] = []
    ignores: List[str] = []
    with session() as s:
        stats = importer_bibliotheques(s, bdd)
        for d in sorted((bdd / "projets").iterdir()):
            if not (d / "parametres.csv").is_file():
                continue
            if not remplacer and s.get(Projet, d.name) is not None:
                ignores.append(d.name)
                continue
            ecrire_projet_complet(s, charger_projet_v1(str(d)), d.name)
            importes.append(d.name)
    return {**stats, "projets_importes": importes, "projets_ignores": ignores}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Importe la base SimTraction V1 (CSV) dans la base de données.")
    ap.add_argument("bdd", nargs="?", default=str(get_settings().v1_bdd_dir), help="dossier BDD de V1")
    ap.add_argument("--remplacer", action="store_true", help="remplacer les projets déjà présents")
    a = ap.parse_args(argv)
    r = importer_bdd_v1(Path(a.bdd), a.remplacer)
    print(f"Bibliothèques : {r['materiel']} engins, {r['sites_ht']} sites HT, {r['normes']} seuils, {r['reglages']} réglages")
    print(f"Projets importés ({len(r['projets_importes'])}) : {', '.join(r['projets_importes']) or '–'}")
    if r["projets_ignores"]:
        print(f"Déjà présents, conservés ({len(r['projets_ignores'])}) : {', '.join(r['projets_ignores'])}")


if __name__ == "__main__":
    sys.exit(main())
