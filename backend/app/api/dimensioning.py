"""
API de dimensionnement – recherche automatique des sous-stations et des postes,
et comparaison des puissances unitaires (variantes).
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.schemas import DimensionnementRequest, TacheEtat
from app.services import calculs
from app.services.bdd_v1 import ProjetIntrouvable

router = APIRouter()


@router.get("/parametres/{project_id}")
def get_parametres(project_id: str) -> Dict[str, Any]:
    """Paramètres par défaut du projet (projet, sinon reglages.csv), sites candidats et variantes."""
    try:
        return calculs.parametres(project_id)
    except ProjetIntrouvable:
        raise HTTPException(status_code=404, detail=f"Projet introuvable : {project_id}")


@router.post("/run", response_model=TacheEtat, status_code=202)
def run_dimensionnement(req: DimensionnementRequest):
    """Lance la recherche en tâche de fond ; le journal de recherche est suivi dans le statut."""
    try:
        return calculs.lancer_dimensionnement(req.project_id, req.model_dump(exclude={"project_id"}))
    except ProjetIntrouvable:
        raise HTTPException(status_code=404, detail=f"Projet introuvable : {req.project_id}")


@router.get("/status/{task_id}", response_model=TacheEtat)
def get_status(task_id: str):
    """Statut, progression et journal de recherche."""
    t = calculs.etat(task_id)
    if t is None or t["type"] != "dimensionnement":
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    return t


@router.get("/result/{task_id}")
def get_result(task_id: str) -> Dict[str, Any]:
    """
    mode « dimensionner » : { D, resultat } ; mode « comparer » : { D, variantes: [...] }.
    Chaque résultat : ok, n, sst, postes, besoins (calibres), cas (marges par situation), essais…
    """
    t = calculs.resultat(task_id)
    if t is None or t["type"] != "dimensionnement":
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    if t["status"] == "error":
        raise HTTPException(status_code=422, detail=t["error"])
    if t["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Calcul non terminé : {t['status']}")
    return t["result"]
