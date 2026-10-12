"""
Projets et bibliothèques en base de données.

Le projet est échangé sous la forme du « dictionnaire projet » de SimTraction V1 (celui que lit le moteur) :
{ id, nom, systeme, duree_s…, trace: {vitesse_ligne, troncons: […]}, trains: […], trafic: […],
  alimentation: {cc, ac, sst: […], postes: […]}, dimensionnement: {…, candidats: […]}, normes: {…} }.
Les valeurs vides des CSV V1 sont stockées à NULL et omises à la lecture : le moteur applique alors ses
valeurs par défaut, exactement comme pour une case vide.
"""

import copy
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db import session as nouvelle_session
from app.db.models import (
    CHAMPS_MATERIEL, CHAMPS_POSTES, CHAMPS_SITES, CHAMPS_SITES_HT, CHAMPS_SST, CHAMPS_TRACE, CHAMPS_TRAFIC, TEXTES,
    Calcul, Circulation, MaterielBibliotheque, MaterielProjet, Norme, Poste, Projet, Reglage, SiteCandidat, SiteHT,
    maintenant,
    SousStation, Troncon,
)
from app.services.bdd_v1 import _parse_num_v1
from app.services.import_v1 import parse_num


class ProjetIntrouvable(LookupError):
    pass


class ConflitVersion(Exception):
    """Le projet a été modifié par ailleurs depuis sa lecture."""

    def __init__(self, version_actuelle: int):
        super().__init__(f"Le projet a été modifié entre-temps (version actuelle {version_actuelle}).")
        self.version_actuelle = version_actuelle


class DonneeInvalide(ValueError):
    pass


# (attribut du projet, classe, champs, chemin dans le dictionnaire projet)
SECTIONS: Dict[str, Tuple[str, Type, List[str]]] = {
    "trace": ("troncons", Troncon, CHAMPS_TRACE),
    "materiel": ("materiel", MaterielProjet, CHAMPS_MATERIEL),
    "trafic": ("trafic", Circulation, CHAMPS_TRAFIC),
    "sous_stations": ("sous_stations", SousStation, CHAMPS_SST),
    "postes": ("postes", Poste, CHAMPS_POSTES),
    "sites": ("sites", SiteCandidat, CHAMPS_SITES),
}
SCALAIRES = ["nom", "systeme", "auteur", "reference", "description", "duree_s", "periode_s", "marge_croisiere"]
NUM_SCALAIRES = {"duree_s", "periode_s", "marge_croisiere"}
SYSTEMES = ("cc3000", "ac1x25", "ac2x25")


# ── Conversions ───────────────────────────────────────────────────────────────

def _sortie(v: Any) -> Any:
    """Nombre en sortie comme le parseur V1 : entier si la valeur est entière."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _entree_num(champ: str, v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise DonneeInvalide(f"{champ} : valeur numérique attendue")
    n = parse_num(v)
    if isinstance(n, str):
        raise DonneeInvalide(f"{champ} : « {v} » n'est pas un nombre")
    return float(n)


def _ligne_vers_dict(obj: Any, champs: Iterable[str]) -> Dict[str, Any]:
    out = {}
    for c in champs:
        v = getattr(obj, c)
        if v is not None:
            out[c] = _sortie(v)
    return out


def _dict_vers_ligne(cls: Type, d: Dict[str, Any], champs: Iterable[str], ordre: int, **cles) -> Any:
    valeurs = {}
    for c in champs:
        v = d.get(c)
        valeurs[c] = ("" if v is None else str(v).strip()) if c in TEXTES else _entree_num(c, v)
    return cls(ordre=ordre, **cles, **valeurs)


def slug(nom: str) -> str:
    """Identifiant de projet à partir de son nom (B.slug en V1)."""
    s = unicodedata.normalize("NFD", str(nom or "projet"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w]+", "_", s, flags=re.ASCII).strip("_")[:50]
    return s or "projet"


def _id_libre(s: Session, nom: str) -> str:
    base, k = slug(nom), 0
    while True:
        pid = base if k == 0 else f"{base}_{k + 1}"
        if s.get(Projet, pid) is None:
            return pid
        k += 1


# ── Dictionnaire projet ↔ base ────────────────────────────────────────────────

def _parametres_depuis_dict(P: Dict[str, Any]) -> Dict[str, Any]:
    """Partie scalaire du projet (parametres.csv hors champs dédiés), sans les listes."""
    par: Dict[str, Any] = {}
    trace = {k: v for k, v in (P.get("trace") or {}).items() if k != "troncons"}
    alim = {k: v for k, v in (P.get("alimentation") or {}).items() if k not in ("sst", "postes")}
    dim = {k: v for k, v in (P.get("dimensionnement") or {}).items() if k != "candidats"}
    if trace:
        par["trace"] = trace
    if alim:
        par["alimentation"] = alim
    if dim:
        par["dimensionnement"] = dim
    par["normes"] = dict(P.get("normes") or {})
    return copy.deepcopy(par)


def _ecrire_lignes(s: Session, p: Projet, section: str, lignes: List[Dict[str, Any]]):
    attr, cls, champs = SECTIONS[section]
    s.execute(delete(cls).where(cls.project_id == p.id))
    s.flush()
    for i, d in enumerate(lignes or []):
        if not isinstance(d, dict):
            raise DonneeInvalide(f"{section} : ligne {i + 1} invalide")
        try:
            s.add(_dict_vers_ligne(cls, d, champs, i, project_id=p.id))
        except DonneeInvalide as e:
            raise DonneeInvalide(f"{section}, ligne {i + 1} : {e}") from None
    s.flush()
    s.expire(p, [attr])


def _appliquer_scalaires(p: Projet, d: Dict[str, Any]):
    for c in SCALAIRES:
        if c not in d:
            continue
        v = d[c]
        if c in NUM_SCALAIRES:
            setattr(p, c, _entree_num(c, v))
        elif c == "systeme":
            if v not in SYSTEMES:
                raise DonneeInvalide(f"systeme : {v!r} (attendu {', '.join(SYSTEMES)})")
            p.systeme = v
        else:
            setattr(p, c, "" if v is None else str(v))
    if not (p.nom or "").strip():
        raise DonneeInvalide("nom : obligatoire")


def ecrire_projet_complet(s: Session, P: Dict[str, Any], pid: Optional[str] = None) -> Projet:
    """Crée (ou remplace) un projet à partir d'un dictionnaire projet complet (import V1, duplication)."""
    pid = pid or P.get("id") or _id_libre(s, P.get("nom") or "projet")
    ancien = s.get(Projet, pid)
    if ancien is not None:
        s.delete(ancien)
        s.flush()
    p = Projet(id=pid, nom=P.get("nom") or pid, systeme=P.get("systeme") or "cc3000", parametres={})
    _appliquer_scalaires(p, {c: P.get(c) for c in SCALAIRES if c in P})
    p.parametres = _parametres_depuis_dict(P)
    d = P.get("_dernier") or {}
    p.dernier_u_min = _entree_num("_dernier.u_min", d.get("u_min"))
    c = d.get("conforme")
    p.dernier_conforme = True if c in (True, "oui") else (False if c in (False, "non") else None)
    s.add(p)
    s.flush()
    alim = P.get("alimentation") or {}
    _ecrire_lignes(s, p, "trace", (P.get("trace") or {}).get("troncons") or [])
    _ecrire_lignes(s, p, "materiel", P.get("trains") or [])
    _ecrire_lignes(s, p, "trafic", P.get("trafic") or [])
    _ecrire_lignes(s, p, "sous_stations", alim.get("sst") or [])
    _ecrire_lignes(s, p, "postes", alim.get("postes") or [])
    _ecrire_lignes(s, p, "sites", (P.get("dimensionnement") or {}).get("candidats") or [])
    return p


def projet_vers_dict(p: Projet) -> Dict[str, Any]:
    """Dictionnaire projet (format du moteur et de la V1)."""
    par = copy.deepcopy(p.parametres or {})
    P: Dict[str, Any] = {"id": p.id}
    for c in SCALAIRES:
        v = getattr(p, c)
        if v is not None:
            P[c] = _sortie(v)
    P["trace"] = {**par.get("trace", {}), "troncons": [_ligne_vers_dict(t, CHAMPS_TRACE) for t in p.troncons]}
    P["trains"] = [_ligne_vers_dict(m, CHAMPS_MATERIEL) for m in p.materiel]
    P["trafic"] = [_ligne_vers_dict(c, CHAMPS_TRAFIC) for c in p.trafic]
    P["alimentation"] = {**par.get("alimentation", {}),
                         "sst": [_ligne_vers_dict(x, CHAMPS_SST) for x in p.sous_stations],
                         "postes": [_ligne_vers_dict(x, CHAMPS_POSTES) for x in p.postes]}
    P["dimensionnement"] = {**par.get("dimensionnement", {}),
                            "candidats": [_ligne_vers_dict(x, CHAMPS_SITES) for x in p.sites]}
    P["normes"] = par.get("normes", {})
    return P


def _avec_lignes():
    return [selectinload(getattr(Projet, a)) for a, _, _ in SECTIONS.values()]


def _lire(s: Session, project_id: str) -> Projet:
    p = s.execute(select(Projet).where(Projet.id == project_id).options(*_avec_lignes())).scalar_one_or_none()
    if p is None:
        raise ProjetIntrouvable(project_id)
    return p


def _meta(p: Projet) -> Dict[str, Any]:
    return {"version": p.version, "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "dernier": {"u_min": p.dernier_u_min, "conforme": p.dernier_conforme}}


# ── Lecture ───────────────────────────────────────────────────────────────────

def lister_projets() -> List[Dict[str, Any]]:
    with nouvelle_session() as s:
        projets = s.execute(select(Projet).options(*_avec_lignes()).order_by(Projet.nom)).scalars().all()
        out = []
        for p in projets:
            longueur = sum(max(0.0, (t.pk_fin or 0.0) - (t.pk_ini or 0.0)) for t in p.troncons)
            out.append({
                "id": p.id, "nom": p.nom, "systeme": p.systeme, "reference": p.reference or "",
                "description": p.description or "", "modifie": p.updated_at.isoformat() if p.updated_at else "",
                "longueur_km": round(longueur, 3), "duree_s": p.duree_s or 3600, "nb_trains": len(p.materiel),
                "nb_circulations": len(p.trafic), "nb_sst": len(p.sous_stations), "nb_postes": len(p.postes),
                "version": p.version, "dernier_u_min": p.dernier_u_min, "dernier_conforme": p.dernier_conforme,
            })
        return out


def charger_projet(project_id: str) -> Dict[str, Any]:
    """Projet complet + métadonnées (_meta : version, dates, dernier calcul)."""
    with nouvelle_session() as s:
        p = _lire(s, project_id)
        return {**projet_vers_dict(p), "_meta": _meta(p)}


def projet_pour_calcul(project_id: str) -> Dict[str, Any]:
    """Projet prêt pour le moteur : seuils de la table des normes, surchargés par ceux du projet."""
    P = charger_projet(project_id)
    P.pop("_meta", None)
    famille = "cc3000" if P.get("systeme") == "cc3000" else "ac25"
    base = {n["code"]: n["valeur"] for n in lister_normes(famille) if n["valeur"] not in ("", None)}
    propres = {k: v for k, v in (P.get("normes") or {}).items() if v not in ("", None)}
    P["normes"] = {**base, **propres}
    return P


# ── Écriture ──────────────────────────────────────────────────────────────────

def _verifier_version(p: Projet, version: Optional[int]):
    if version is not None and version != p.version:
        raise ConflitVersion(p.version)


def modifier_section(project_id: str, section: str, donnees: Any, version: Optional[int]) -> Dict[str, Any]:
    """
    Remplace une partie du projet. Sections : informations (champs scalaires), parametres (arbre de
    paramètres : trace.vitesse_ligne, alimentation.cc/ac, dimensionnement, normes), et les tableaux
    trace, materiel, trafic, sous_stations, postes, sites. Incrémente la version.
    """
    with nouvelle_session() as s:
        p = _lire(s, project_id)
        _verifier_version(p, version)
        if section == "informations":
            if not isinstance(donnees, dict):
                raise DonneeInvalide("informations : objet attendu")
            _appliquer_scalaires(p, donnees)
        elif section == "parametres":
            if not isinstance(donnees, dict):
                raise DonneeInvalide("parametres : objet attendu")
            p.parametres = _parametres_depuis_dict(donnees)
        elif section in SECTIONS:
            if not isinstance(donnees, list):
                raise DonneeInvalide(f"{section} : liste attendue")
            _ecrire_lignes(s, p, section, donnees)
        else:
            raise DonneeInvalide(f"section inconnue : {section}")
        p.version += 1
        p.updated_at = maintenant()
        s.flush()
        s.refresh(p)
        p = _lire(s, project_id)
        return {**projet_vers_dict(p), "_meta": _meta(p)}


def creer_projet(nom: str, systeme: str = "cc3000", copie_de: Optional[str] = None) -> Dict[str, Any]:
    """Nouveau projet vierge (valeurs de reglages.csv, comme projetVierge en V1) ou copie d'un projet (variante)."""
    if copie_de:
        P = charger_projet(copie_de)
        P.pop("_meta", None)
        P["nom"] = nom
        P.pop("_dernier", None)
    else:
        if systeme not in SYSTEMES:
            raise DonneeInvalide(f"systeme : {systeme!r} (attendu {', '.join(SYSTEMES)})")
        P = projet_vierge(nom, systeme, lire_reglages())
    with nouvelle_session() as s:
        pid = _id_libre(s, nom)
        P["id"] = pid
        ecrire_projet_complet(s, P, pid)
    return charger_projet(pid)


def supprimer_projet(project_id: str):
    with nouvelle_session() as s:
        p = s.get(Projet, project_id)
        if p is None:
            raise ProjetIntrouvable(project_id)
        s.delete(p)


def enregistrer_dernier_calcul(project_id: str, u_min: Optional[float], conforme: Optional[bool]):
    """Résultat du dernier calcul (affiché dans la liste des projets) ; ne change pas la version."""
    with nouvelle_session() as s:
        p = s.get(Projet, project_id)
        if p is not None:
            p.dernier_u_min, p.dernier_conforme = u_min, conforme


def projet_vierge(nom: str, systeme: str, reglages: Dict[str, Any]) -> Dict[str, Any]:
    """projetVierge de V1 : tracé de 30 km entre deux gares, paramètres de reglages.csv."""
    def reg(code: str, defaut: Any = "") -> Any:
        v = reglages.get(code)
        return defaut if v in ("", None) else v

    return {
        "nom": nom, "auteur": "", "reference": "", "description": "", "systeme": systeme,
        "duree_s": reg("sim.duree_s", 3600), "periode_s": reg("sim.periode_s", 0),
        "marge_croisiere": reg("sim.marge_croisiere", 0.98), "normes": {},
        "trace": {"vitesse_ligne": 0, "troncons": [
            {"pk_ini": 0, "pk_fin": 0.5, "pente": 0, "rayon": 0, "limite": 0, "gare": "Gare A", "tunnel": 0},
            {"pk_ini": 0.5, "pk_fin": 29.5, "pente": 0, "rayon": 0, "limite": 0, "gare": "", "tunnel": 0},
            {"pk_ini": 29.5, "pk_fin": 30, "pente": 0, "rayon": 0, "limite": 0, "gare": "Gare B", "tunnel": 0},
        ]},
        "trains": [], "trafic": [],
        "alimentation": {
            "cc": {"r_cat": reg("cc.r_cat"), "r_rail": reg("cc.r_rail"), "nb_voies": reg("cc.nb_voies", 2),
                   "g_rail_terre": reg("cc.g_rail_terre"), "section_mm2": reg("cc.section_mm2"),
                   "i_adm_a": reg("cc.i_adm_a", 0)},
            "ac": {k: reg("ac." + k) for k in ("u0", "zc_r", "zc_x", "zf_r", "zf_x", "zcf_r", "zcf_x", "s_at_mva", "ucc_at_pct")}
                  | {"nb_voies": reg("ac.nb_voies", 2)},
            "sst": [], "postes": [],
        },
        "dimensionnement": {"candidats": [], "pas_min_km": "", "pas_max_km": "", "puissances": "", "surcharge_n": "",
                            "surcharge_n1": "", "surcharge_pointe": "", "n1": "oui", "pas_ps_km": "", "pas_at_km": "",
                            "dt": 5, "variantes": "", "chute_pct": ""},
    }


# ── Bibliothèques ─────────────────────────────────────────────────────────────

def lister_materiel() -> List[Dict[str, Any]]:
    with nouvelle_session() as s:
        rows = s.execute(select(MaterielBibliotheque).order_by(MaterielBibliotheque.ordre)).scalars().all()
        return [_ligne_vers_dict(m, CHAMPS_MATERIEL) for m in rows]


def lister_sites_ht() -> List[Dict[str, Any]]:
    with nouvelle_session() as s:
        rows = s.execute(select(SiteHT).order_by(SiteHT.ordre)).scalars().all()
        return [{c: _sortie(getattr(r, c)) if getattr(r, c) is not None else "" for c in CHAMPS_SITES_HT} for r in rows]


def lister_normes(systeme: Optional[str] = None) -> List[Dict[str, Any]]:
    with nouvelle_session() as s:
        q = select(Norme).order_by(Norme.ordre)
        if systeme:
            q = q.where(Norme.systeme == systeme)
        return [{"systeme": n.systeme, "code": n.code, "libelle": n.libelle,
                 "valeur": _sortie(n.valeur) if n.valeur is not None else "", "reference": n.reference}
                for n in s.execute(q).scalars().all()]


def lire_reglages() -> Dict[str, Any]:
    """Réglages par défaut : code → valeur, convertie comme parseNum en V1."""
    with nouvelle_session() as s:
        return {r.code: _parse_num_v1(r.valeur) for r in s.execute(select(Reglage)).scalars().all()}


def base_vide() -> bool:
    with nouvelle_session() as s:
        return s.execute(select(func.count()).select_from(Projet)).scalar_one() == 0 and \
            s.execute(select(func.count()).select_from(Reglage)).scalar_one() == 0


# ── Historique des calculs ────────────────────────────────────────────────────

def enregistrer_calcul(t: Dict[str, Any]):
    from datetime import datetime, timezone

    def date(x):
        return datetime.fromtimestamp(x, timezone.utc) if x else None

    with nouvelle_session() as s:
        s.merge(Calcul(
            id=t["task_id"], project_id=t["project_id"], type=t["type"], opts=t.get("opts") or {},
            status=t["status"], error=t.get("error"), journal=t.get("journal") or [], u_min=t.get("u_min"),
            conforme=t.get("conforme"), duree_s=(t["finished_at"] - t["started_at"]) if t.get("started_at") else None,
            created_at=date(t.get("created_at")), finished_at=date(t.get("finished_at")), resultat=t.get("result"),
        ))


def lire_calcul(task_id: str, avec_resultat: bool = True) -> Optional[Dict[str, Any]]:
    """Calcul terminé conservé en base (après un redémarrage du serveur)."""
    with nouvelle_session() as s:
        c = s.get(Calcul, task_id)
        if c is None:
            return None
        out = {"task_id": c.id, "type": c.type, "project_id": c.project_id or "", "opts": c.opts or {},
               "status": c.status, "progress": 100.0, "message": "Terminé" if c.status == "done" else "Erreur",
               "error": c.error, "journal": c.journal or [],
               "created_at": c.created_at.timestamp() if c.created_at else 0.0,
               "started_at": None, "finished_at": c.finished_at.timestamp() if c.finished_at else None}
        if avec_resultat:
            out["result"] = c.resultat
        return out


def historique(project_id: str, limite: int = 20) -> List[Dict[str, Any]]:
    with nouvelle_session() as s:
        q = (select(Calcul.id, Calcul.type, Calcul.status, Calcul.u_min, Calcul.conforme, Calcul.duree_s,
                    Calcul.created_at, Calcul.opts, Calcul.error)
             .where(Calcul.project_id == project_id).order_by(Calcul.created_at.desc()).limit(limite))
        return [{"task_id": r.id, "type": r.type, "status": r.status, "u_min": r.u_min, "conforme": r.conforme,
                 "duree_s": r.duree_s, "created_at": r.created_at.isoformat() if r.created_at else None,
                 "opts": {k: v for k, v in (r.opts or {}).items() if k != "alimentation"}, "error": r.error}
                for r in s.execute(q).all()]
