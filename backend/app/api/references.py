from typing import List, Optional

from fastapi import APIRouter

from app.schemas import Norme, SiteHT
from app.services.projets import lister_normes, lister_sites_ht

router = APIRouter()


@router.get("/normes", response_model=List[Norme])
def list_normes(systeme: Optional[str] = None):
    """Seuils normatifs par défaut (EN 50163, EN 50388-1…), filtrables par système (cc3000 / ac25)."""
    return lister_normes(systeme)


@router.get("/sites-ht", response_model=List[SiteHT])
def list_sites_ht():
    """Postes HT où une sous-station peut être raccordée, avec leur puissance de court-circuit."""
    return lister_sites_ht()
