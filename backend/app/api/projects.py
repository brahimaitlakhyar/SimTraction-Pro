from fastapi import APIRouter, HTTPException
from typing import List, Optional
import json, os

router = APIRouter()

# In a production app, these would use SQLAlchemy ORM with a real DB.
# For now, data is loaded from CSV/JSON project files (V1 compatibility).

DATA_DIR = os.getenv("DATA_DIR", "./data")

@router.get("/")
async def list_projects():
    """Liste tous les projets disponibles."""
    projects_file = os.path.join(DATA_DIR, "projets.json")
    if os.path.exists(projects_file):
        with open(projects_file, encoding="utf-8") as f:
            return json.load(f)
    # Return sample data if no projects file
    return [
        {"id": "ain_sebaa_kenitra", "name": "Ain Sébaâ – Kénitra", "system": "AC25kV_2x25", "status": "ready"},
        {"id": "casa_rabat_tgv", "name": "Casa – Rabat (TGV)", "system": "AC25kV_2x25", "status": "ready"},
        {"id": "marrakech_agadir", "name": "Marrakech – Agadir", "system": "AC25kV_1x25", "status": "ready"},
    ]

@router.get("/{project_id}")
async def get_project(project_id: str):
    """Récupère les détails d'un projet."""
    return {"id": project_id, "name": project_id.replace("_", " ").title()}

@router.post("/")
async def create_project(data: dict):
    """Crée un nouveau projet."""
    return {"id": "new_project", "message": "Projet créé avec succès", **data}
