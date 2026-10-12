"""
Exécution des calculs en tâche de fond : étude (normale + N-1), dimensionnement, comparaison de variantes.
Implémentation en mémoire (pool de threads) en attendant la file Celery + Redis (plan, phase 3.2) :
les tâches sont perdues au redémarrage du serveur.
"""

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from app.core.config import get_settings
from app.physics import SimulationEnv, executer_etude, json_sur
from app.physics.dimensioning import comparer_variantes, dimensionner, liste_variantes, parametres_dimensionnement
from app.services.bdd_v1 import lire_reglages, projet_pour_calcul

_executor = ThreadPoolExecutor(max_workers=get_settings().simulation_workers, thread_name_prefix="calcul")
_taches: Dict[str, Dict[str, Any]] = {}
_verrou = threading.Lock()
_MAX_TACHES = 50  # les plus anciennes tâches terminées sont oubliées au-delà
_MAX_JOURNAL = 2000

Progression = Callable[[float, str], None]
Journal = Callable[[str], None]


def _maj(task_id: str, **champs):
    with _verrou:
        _taches[task_id].update(champs)


def _journal(task_id: str, ligne: str):
    with _verrou:
        j = _taches[task_id]["journal"]
        if len(j) < _MAX_JOURNAL:
            j.append(ligne)


def _projet(project_id: str, alimentation: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Projet de la base, avec éventuellement une alimentation proposée (non enregistrée)."""
    P = projet_pour_calcul(project_id)
    if alimentation:
        P["alimentation"] = {**(P.get("alimentation") or {}), **alimentation}
    return P


def _etude(project_id: str, opts: Dict[str, Any], prog: Progression, _log: Journal) -> Dict[str, Any]:
    o = dict(opts)
    env = SimulationEnv(_projet(project_id, o.pop("alimentation", None)))
    return executer_etude(env, o, prog)


def _dimensionnement(project_id: str, opts: Dict[str, Any], prog: Progression, log: Journal) -> Dict[str, Any]:
    P = projet_pour_calcul(project_id)
    D = parametres_dimensionnement(P, lire_reglages())
    D.update({k: v for k, v in (opts.get("parametres") or {}).items() if v not in ("", None)})
    env = SimulationEnv(P)
    if opts.get("mode") == "comparer":
        variantes = liste_variantes(D)
        if not variantes:
            raise ValueError("Indiquez au moins une puissance unitaire à comparer (ex. 3000 ; 6000).")
        res = comparer_variantes(env, variantes, D, lambda f: prog(f, "Comparaison des variantes…"), log)
        return {"mode": "comparer", "D": D, "variantes": res, "famille": env.famille, "systeme": env.systeme}
    r = dimensionner(env, D, lambda f: prog(f, "Recherche des sous-stations…"), log)
    return {"mode": "dimensionner", "D": D, "resultat": r, "famille": env.famille, "systeme": env.systeme}


_TYPES = {"etude": _etude, "dimensionnement": _dimensionnement}


def _executer(task_id: str, type_: str, project_id: str, opts: Dict[str, Any]):
    _maj(task_id, status="running", started_at=time.time())
    try:
        res = _TYPES[type_](project_id, opts,
                            lambda f, txt: _maj(task_id, progress=round(100 * f, 1), message=txt),
                            lambda ligne: _journal(task_id, ligne))
        _maj(task_id, status="done", progress=100.0, message="Terminé", result=json_sur(res), finished_at=time.time())
    except Exception as e:  # erreur métier ou bug : renvoyée à l'interface
        _maj(task_id, status="error", error=str(e), detail=traceback.format_exc(limit=5), finished_at=time.time())


def _purger():
    with _verrou:
        finies = sorted((t for t in _taches.values() if t["status"] in ("done", "error")), key=lambda t: t["created_at"])
        for t in finies[: max(0, len(_taches) - _MAX_TACHES)]:
            del _taches[t["task_id"]]


def lancer(type_: str, project_id: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    projet_pour_calcul(project_id)  # erreur immédiate si le projet n'existe pas
    _purger()
    task_id = str(uuid.uuid4())
    with _verrou:
        _taches[task_id] = {"task_id": task_id, "type": type_, "project_id": project_id, "opts": opts,
                            "status": "queued", "progress": 0.0, "message": "En attente…", "error": None,
                            "journal": [], "result": None, "created_at": time.time()}
    _executor.submit(_executer, task_id, type_, project_id, opts)
    return etat(task_id)


def lancer_etude(project_id: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    return lancer("etude", project_id, opts)


def lancer_dimensionnement(project_id: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    return lancer("dimensionnement", project_id, opts)


def etat(task_id: str) -> Optional[Dict[str, Any]]:
    """État d'une tâche sans le résultat (léger, pour le suivi de progression)."""
    with _verrou:
        t = _taches.get(task_id)
        if t is None:
            return None
        out = {k: v for k, v in t.items() if k not in ("result", "detail")}
        out["journal"] = list(t["journal"])
        return out


def resultat(task_id: str) -> Optional[Dict[str, Any]]:
    with _verrou:
        return _taches.get(task_id)


def parametres(project_id: str) -> Dict[str, Any]:
    """Paramètres de dimensionnement par défaut d'un projet (formulaire)."""
    P = projet_pour_calcul(project_id)
    D = parametres_dimensionnement(P, lire_reglages())
    return {"parametres": {k: v for k, v in D.items() if k != "candidats"},
            "candidats": D.get("candidats") or [], "variantes": liste_variantes(D), "systeme": P.get("systeme")}


__all__: List[str] = ["lancer_etude", "lancer_dimensionnement", "etat", "resultat", "parametres"]
