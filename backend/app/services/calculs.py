"""
Exécution des études en tâche de fond.
Implémentation en mémoire (pool de threads) en attendant la file Celery + Redis (plan, phase 3.2) :
les tâches sont perdues au redémarrage du serveur.
"""

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.physics import SimulationEnv, executer_etude, json_sur
from app.services.bdd_v1 import projet_pour_calcul

_executor = ThreadPoolExecutor(max_workers=get_settings().simulation_workers, thread_name_prefix="etude")
_taches: Dict[str, Dict[str, Any]] = {}
_verrou = threading.Lock()
_MAX_TACHES = 50  # les plus anciennes tâches terminées sont oubliées au-delà


def _maj(task_id: str, **champs):
    with _verrou:
        _taches[task_id].update(champs)


def _executer(task_id: str, project_id: str, opts: Dict[str, Any]):
    _maj(task_id, status="running", started_at=time.time())
    try:
        env = SimulationEnv(projet_pour_calcul(project_id))
        res = executer_etude(env, opts, lambda f, txt: _maj(task_id, progress=round(100 * f, 1), message=txt))
        _maj(task_id, status="done", progress=100.0, message="Terminé", result=json_sur(res), finished_at=time.time())
    except Exception as e:  # erreur métier ou bug : renvoyée à l'interface
        _maj(task_id, status="error", error=str(e), detail=traceback.format_exc(limit=5), finished_at=time.time())


def _purger():
    with _verrou:
        finies = sorted((t for t in _taches.values() if t["status"] in ("done", "error")), key=lambda t: t["created_at"])
        for t in finies[: max(0, len(_taches) - _MAX_TACHES)]:
            del _taches[t["task_id"]]


def lancer_etude(project_id: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    projet_pour_calcul(project_id)  # erreur immédiate si le projet n'existe pas
    _purger()
    task_id = str(uuid.uuid4())
    with _verrou:
        _taches[task_id] = {"task_id": task_id, "project_id": project_id, "opts": opts, "status": "queued",
                            "progress": 0.0, "message": "En attente…", "error": None, "result": None,
                            "created_at": time.time()}
    _executor.submit(_executer, task_id, project_id, opts)
    return etat(task_id)


def etat(task_id: str) -> Optional[Dict[str, Any]]:
    """État d'une tâche sans le résultat (léger, pour le suivi de progression)."""
    with _verrou:
        t = _taches.get(task_id)
        return None if t is None else {k: v for k, v in t.items() if k not in ("result", "detail")}


def resultat(task_id: str) -> Optional[Dict[str, Any]]:
    with _verrou:
        return _taches.get(task_id)
