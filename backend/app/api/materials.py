from typing import List

from fastapi import APIRouter

from app.schemas import Materiel
from app.services.bdd_v1 import lister_materiel

router = APIRouter()


@router.get("/", response_model=List[Materiel])
def list_materials():
    """Bibliothèque commune du matériel roulant (BDD/materiel.csv)."""
    return lister_materiel()
