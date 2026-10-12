from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.schemas import ProjetResume
from app.services.bdd_v1 import ProjetIntrouvable, charger_projet, lister_projets

router = APIRouter()

# Lecture seule depuis la BDD V1 (CSV) ; création / modification avec la persistance PostgreSQL (phase 1).


@router.get("/", response_model=List[ProjetResume])
def list_projects():
    """Liste des projets de la base."""
    return lister_projets()


@router.get("/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    """Projet complet : paramètres, tracé, matériel, trafic, alimentation, sites candidats."""
    try:
        return charger_projet(project_id)
    except ProjetIntrouvable:
        raise HTTPException(status_code=404, detail=f"Projet introuvable : {project_id}")
