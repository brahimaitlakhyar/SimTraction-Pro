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


class SimulationRequest(BaseModel):
    project_id: str
    dt: float = Field(5.0, ge=0.5, le=10.0, description="Pas de temps de la simulation (s)")
    couplage: bool = Field(True, description="Effort des engins dépendant de la tension au pantographe")
    n1: Union[bool, Literal["interm"]] = Field(
        True, description="Situations N-1 : toutes les SST (true), intermédiaires seulement (\"interm\") ou aucune (false)")


class TacheEtat(BaseModel):
    task_id: str
    project_id: str
    opts: Dict[str, Any]
    status: Literal["queued", "running", "done", "error"]
    progress: float
    message: str
    error: Optional[str] = None
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


__all__ = ["Systeme", "ProjetResume", "SimulationRequest", "TacheEtat", "Materiel", "Norme", "SiteHT", "List"]
