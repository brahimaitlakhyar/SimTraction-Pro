"""Schémas Pydantic de l'API (entrées et sorties)."""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

Systeme = Literal["cc3000", "ac1x25", "ac2x25"]


class ProjetResume(BaseModel):
    id: str
    nom: str
    systeme: Systeme
    reference: str = ""
    description: str = ""
    modifie: str = ""
    longueur_km: float
    duree_s: float
    nb_trains: int
    nb_circulations: int
    nb_sst: int
    nb_postes: int


class Alimentation(BaseModel):
    """Sous-stations et postes proposés (ex. solution de dimensionnement), non enregistrés dans le projet."""
    sst: List[Dict[str, Any]]
    postes: List[Dict[str, Any]] = []


class SimulationRequest(BaseModel):
    project_id: str
    dt: float = Field(5.0, ge=0.5, le=10.0, description="Pas de temps de la simulation (s)")
    couplage: bool = Field(True, description="Effort des engins dépendant de la tension au pantographe")
    n1: Union[bool, Literal["interm"]] = Field(
        True, description="Situations N-1 : toutes les SST (true), intermédiaires seulement (\"interm\") ou aucune (false)")
    alimentation: Optional[Alimentation] = Field(
        None, description="Alimentation à vérifier à la place de celle du projet (sans l'enregistrer)")


class DimensionnementRequest(BaseModel):
    project_id: str
    mode: Literal["dimensionner", "comparer"] = Field(
        "dimensionner", description="Recherche à puissance adaptée, ou comparaison des puissances unitaires (variantes)")
    parametres: Dict[str, Any] = Field(
        default_factory=dict,
        description="Surcharges des paramètres : pas_min_km, pas_max_km, puissances, surcharge_n, surcharge_n1, "
                    "surcharge_pointe, n1, dt, variantes, chute_pct, pas_ps_km, pas_at_km")


class TacheEtat(BaseModel):
    task_id: str
    type: Literal["etude", "dimensionnement"]
    project_id: str
    opts: Dict[str, Any]
    status: Literal["queued", "running", "done", "error"]
    progress: float
    message: str
    error: Optional[str] = None
    journal: List[str] = []
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class Materiel(BaseModel):
    ref: Union[int, float, str]
    nom: str
    type: str
    masse_t: Any = None
    v_max: Any = None
    p_max_kw: Any = None
    u_nom: Any = None

    model_config = {"extra": "allow"}


class Norme(BaseModel):
    systeme: str
    code: str
    libelle: str
    valeur: Any
    reference: str


class SiteHT(BaseModel):
    ligne: str
    nom: str
    pk: Any
    scc_mva: Any
    tension_kv: Any
    remarque: str


__all__ = ["Systeme", "ProjetResume", "Alimentation", "SimulationRequest", "DimensionnementRequest", "TacheEtat", "Materiel", "Norme", "SiteHT", "List"]
