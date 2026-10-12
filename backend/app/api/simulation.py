"""
API de simulation – Lance et récupère les résultats de simulation.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid, asyncio, time

router = APIRouter()

# In-memory task store (replace with Redis/Celery in production)
_tasks: Dict[str, Dict] = {}


class SimulationRequest(BaseModel):
    project_id: str
    system_type: str = "AC25kV_2x25"  # DC1500, DC3000, AC25kV_1x25, AC25kV_2x25
    peak_hour_trains: int = 8
    headway_min: float = 7.5
    apply_n1: bool = True
    regenerative_braking: bool = True
    extra_params: Optional[Dict[str, Any]] = None


async def _run_simulation(task_id: str, req: SimulationRequest):
    """Simulate asynchronously (mock – replace with real physics engine call)."""
    _tasks[task_id]["status"] = "running"
    _tasks[task_id]["progress"] = 0
    try:
        # Simulate computation delay
        for i in range(1, 11):
            await asyncio.sleep(0.5)
            _tasks[task_id]["progress"] = i * 10

        # Mock result (replace with actual physics engine output)
        _tasks[task_id]["result"] = {
            "v_min_kV": 18.4,
            "v_max_kV": 27.5,
            "i_max_A": 1240,
            "energy_mwh": 14.7,
            "recovered_mwh": 3.2,
            "n1_compliant": True,
            "voltage_compliant": True,
            "duration_s": 5.2,
            "trains_simulated": req.peak_hour_trains,
        }
        _tasks[task_id]["status"] = "done"
    except Exception as e:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = str(e)


@router.post("/run")
async def run_simulation(req: SimulationRequest, background_tasks: BackgroundTasks):
    """Lance une simulation et retourne un task_id pour suivi."""
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status": "queued", "progress": 0, "result": None}
    background_tasks.add_task(_run_simulation, task_id, req)
    return {"task_id": task_id, "status": "queued"}


@router.get("/status/{task_id}")
async def get_status(task_id: str):
    """Retourne le statut et la progression d'une simulation."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    return _tasks[task_id]


@router.get("/result/{task_id}")
async def get_result(task_id: str):
    """Retourne les résultats complets d'une simulation terminée."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    task = _tasks[task_id]
    if task["status"] != "done":
        raise HTTPException(status_code=202, detail=f"Simulation en cours: {task['status']}")
    return task["result"]
