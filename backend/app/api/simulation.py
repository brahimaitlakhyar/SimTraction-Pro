"""
API de simulation – lance une étude (situation normale + N-1) et en récupère les résultats.
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.schemas import SimulationRequest, TacheEtat
from app.services import calculs
from app.services.projets import ProjetIntrouvable

router = APIRouter()


@router.post("/run", response_model=TacheEtat, status_code=202)
def run_simulation(req: SimulationRequest):
    """Lance l'étude en tâche de fond et retourne la tâche à suivre."""
    try:
        return calculs.lancer_etude(req.project_id, req.model_dump(exclude={"project_id"}, exclude_none=True))
    except ProjetIntrouvable:
        raise HTTPException(status_code=404, detail=f"Projet introuvable : {req.project_id}")


@router.get("/status/{task_id}", response_model=TacheEtat)
def get_status(task_id: str):
    """Statut et progression (0 → 100 %) d'une étude."""
    t = calculs.etat(task_id)
    if t is None or t["type"] != "etude":
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    return t


@router.get("/result/{task_id}")
def get_result(task_id: str) -> Dict[str, Any]:
    """
    Résultats d'une étude terminée : A (analyse : glob, sst, trains, zones), conf (conformité),
    n1 (situations dégradées), series (graphiques), avert, opts, duree.
    """
    t = calculs.resultat(task_id)
    if t is None or t["type"] != "etude":
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    if t["status"] == "error":
        raise HTTPException(status_code=422, detail=t["error"])
    if t["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Étude non terminée : {t['status']}")
    return t["result"]
