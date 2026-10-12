"""
Modèle de données. Les tables de projet reprennent une à une les fichiers CSV de SimTraction V1
(mêmes champs, même ordre des lignes), pour une rétrocompatibilité exacte avec la BDD V1 et le moteur.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonType = JSON().with_variant(JSONB(), "postgresql")


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Champs des lignes de projet (noms identiques au moteur et aux CSV V1) ─────────────

CHAMPS_TRACE = ["pk_ini", "pk_fin", "pente", "rayon", "limite", "gare", "tunnel"]
CHAMPS_MATERIEL = [
    "ref", "nom", "type", "masse_t", "masse_dyn_t", "longueur_m", "f_max", "v1", "v_max", "p_max_kw", "rendement",
    "p_aux_kw", "cos_phi", "u_nom", "davis_a", "davis_b", "davis_c", "coef_courbe", "c2_ohm", "c3", "i_aux",
    "f_frein", "p_frein_kw", "rendement_recup", "decel_service",
]
CHAMPS_TRAFIC = ["ref_train", "sens", "depart", "voie", "v_initiale", "arrets", "libelle"]
CHAMPS_SST = ["nom", "pk", "en_service", "u0", "r_int", "p_nom_kw", "s_nom_mva", "ucc_pct", "scc_mva"]
CHAMPS_POSTES = ["nom", "pk", "type", "at"]
CHAMPS_SITES = ["nom", "pk", "scc_mva"]
CHAMPS_SITES_HT = ["ligne", "nom", "pk", "scc_mva", "tension_kv", "remarque"]

TEXTES = {"gare", "nom", "type", "depart", "arrets", "libelle", "en_service", "at", "ligne", "remarque"}


# Colonnes numériques du matériel roulant (partagées par la bibliothèque et les projets)
_ColonnesMateriel = type("_ColonnesMateriel", (), {
    c: mapped_column(Float, nullable=True) for c in CHAMPS_MATERIEL if c not in ("nom", "type")
})


class Projet(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # nom de dossier V1 (slug)
    nom: Mapped[str] = mapped_column(String(200))
    systeme: Mapped[str] = mapped_column(String(10))  # cc3000 / ac1x25 / ac2x25
    auteur: Mapped[str] = mapped_column(String(200), default="")
    reference: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    duree_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    periode_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    marge_croisiere: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Paramètres scalaires de parametres.csv : trace.vitesse_ligne, alimentation.cc / ac,
    # dimensionnement (hors sites), seuils normatifs propres au projet
    parametres: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict)
    dernier_u_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dernier_conforme: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)  # verrou optimiste
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant, onupdate=maintenant)

    troncons: Mapped[List["Troncon"]] = relationship(order_by="Troncon.ordre", cascade="all, delete-orphan")
    materiel: Mapped[List["MaterielProjet"]] = relationship(order_by="MaterielProjet.ordre", cascade="all, delete-orphan")
    trafic: Mapped[List["Circulation"]] = relationship(order_by="Circulation.ordre", cascade="all, delete-orphan")
    sous_stations: Mapped[List["SousStation"]] = relationship(order_by="SousStation.ordre", cascade="all, delete-orphan")
    postes: Mapped[List["Poste"]] = relationship(order_by="Poste.ordre", cascade="all, delete-orphan")
    sites: Mapped[List["SiteCandidat"]] = relationship(order_by="SiteCandidat.ordre", cascade="all, delete-orphan")


class _LigneProjet:
    """Ligne ordonnée rattachée à un projet."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ordre: Mapped[int] = mapped_column(Integer)


def _fk_projet():
    return mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), index=True)


class Troncon(_LigneProjet, Base):
    __tablename__ = "track_sections"
    project_id: Mapped[str] = _fk_projet()
    pk_ini: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pk_fin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pente: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rayon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    limite: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gare: Mapped[str] = mapped_column(String(200), default="")
    tunnel: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class MaterielProjet(_ColonnesMateriel, _LigneProjet, Base):
    __tablename__ = "rolling_stock"
    project_id: Mapped[str] = _fk_projet()
    nom: Mapped[str] = mapped_column(String(200), default="")
    type: Mapped[str] = mapped_column(String(20), default="tabule")


class Circulation(_LigneProjet, Base):
    __tablename__ = "timetables"
    project_id: Mapped[str] = _fk_projet()
    ref_train: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depart: Mapped[str] = mapped_column(String(20), default="")
    voie: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    v_initiale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    arrets: Mapped[str] = mapped_column(Text, default="")
    libelle: Mapped[str] = mapped_column(String(200), default="")


class SousStation(_LigneProjet, Base):
    __tablename__ = "substations"
    project_id: Mapped[str] = _fk_projet()
    nom: Mapped[str] = mapped_column(String(200), default="")
    pk: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    en_service: Mapped[str] = mapped_column(String(10), default="oui")
    u0: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    r_int: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_nom_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    s_nom_mva: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ucc_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scc_mva: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Poste(_LigneProjet, Base):
    __tablename__ = "switching_stations"
    project_id: Mapped[str] = _fk_projet()
    nom: Mapped[str] = mapped_column(String(200), default="")
    pk: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    type: Mapped[str] = mapped_column(String(10), default="PS")  # PS, SP, SSP, ATS
    at: Mapped[str] = mapped_column(String(10), default="")


class SiteCandidat(_LigneProjet, Base):
    __tablename__ = "candidate_sites"
    project_id: Mapped[str] = _fk_projet()
    nom: Mapped[str] = mapped_column(String(200), default="")
    pk: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scc_mva: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


# ── Bibliothèques communes ─────────────────────────────────────────────────────

class MaterielBibliotheque(_ColonnesMateriel, _LigneProjet, Base):
    __tablename__ = "rolling_stock_library"
    nom: Mapped[str] = mapped_column(String(200), default="")
    type: Mapped[str] = mapped_column(String(20), default="tabule")


class SiteHT(_LigneProjet, Base):
    __tablename__ = "hv_sites"
    ligne: Mapped[str] = mapped_column(String(200), default="")
    nom: Mapped[str] = mapped_column(String(200), default="")
    pk: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scc_mva: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tension_kv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remarque: Mapped[str] = mapped_column(String(500), default="")


class Norme(_LigneProjet, Base):
    __tablename__ = "standards"
    systeme: Mapped[str] = mapped_column(String(10))  # cc3000 / ac25
    code: Mapped[str] = mapped_column(String(64))
    libelle: Mapped[str] = mapped_column(String(300), default="")
    valeur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference: Mapped[str] = mapped_column(String(300), default="")


class Reglage(_LigneProjet, Base):
    __tablename__ = "settings"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    libelle: Mapped[str] = mapped_column(String(300), default="")
    valeur: Mapped[str] = mapped_column(String(300), default="")  # texte brut (ex. « 3000/6000 », « 0,98 »)


# ── Historique des calculs ─────────────────────────────────────────────────────

class Calcul(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # identifiant de tâche
    project_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)  # conservé après suppression du projet
    type: Mapped[str] = mapped_column(String(20))  # etude / dimensionnement
    opts: Mapped[Dict[str, Any]] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(10))  # done / error
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    journal: Mapped[List[str]] = mapped_column(JsonType, default=list)
    u_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conforme: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    duree_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resultat: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)
