from typing import List

from fastapi import APIRouter

from app.schemas import Materiel
from app.services.projets import lister_materiel

router = APIRouter()


@router.get("/", response_model=List[Materiel])
def list_materials():
    """Bibliothèque commune du matériel roulant."""
    return lister_materiel()
