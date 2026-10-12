from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Response

from app.schemas import ProjetCreation, ProjetResume, SectionModification
from app.services import projets
from app.services.projets import ConflitVersion, DonneeInvalide, ProjetIntrouvable

router = APIRouter()

SECTIONS = ["informations", "parametres", "trace", "materiel", "trafic", "sous_stations", "postes", "sites"]


def _introuvable(project_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Projet introuvable : {project_id}")


@router.get("/", response_model=List[ProjetResume])
def list_projects():
    """Liste des projets, avec le résultat de leur dernier calcul."""
    return projets.lister_projets()


@router.post("/", status_code=201)
def create_project(req: ProjetCreation) -> Dict[str, Any]:
    """Nouveau projet vierge (réglages par défaut) ou variante d'un projet existant (`copie_de`)."""
    try:
        return projets.creer_projet(req.nom, req.systeme, req.copie_de)
    except ProjetIntrouvable:
        raise _introuvable(req.copie_de or "")
    except DonneeInvalide as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    """Projet complet (format V1 / moteur) ; `_meta` donne la version à renvoyer lors d'une modification."""
    try:
        return projets.charger_projet(project_id)
    except ProjetIntrouvable:
        raise _introuvable(project_id)


@router.put("/{project_id}/{section}")
def update_section(project_id: str, section: str, req: SectionModification) -> Dict[str, Any]:
    """
    Remplace une partie du projet :
    - `informations` : nom, systeme, auteur, reference, description, duree_s, periode_s, marge_croisiere ;
    - `parametres` : {trace: {vitesse_ligne}, alimentation: {cc, ac}, dimensionnement: {…}, normes: {…}} ;
    - `trace`, `materiel`, `trafic`, `sous_stations`, `postes`, `sites` : liste complète des lignes.

    `version` doit être celle lue avec le projet : sinon 409 (projet modifié entre-temps).
    """
    if section not in SECTIONS:
        raise HTTPException(status_code=404, detail=f"Section inconnue : {section} (attendu : {', '.join(SECTIONS)})")
    try:
        return projets.modifier_section(project_id, section, req.donnees, req.version)
    except ProjetIntrouvable:
        raise _introuvable(project_id)
    except ConflitVersion as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DonneeInvalide as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str):
    try:
        projets.supprimer_projet(project_id)
    except ProjetIntrouvable:
        raise _introuvable(project_id)
    return Response(status_code=204)


@router.get("/{project_id}/historique")
def get_history(project_id: str, limite: int = 20) -> List[Dict[str, Any]]:
    """Derniers calculs du projet (études et dimensionnements), du plus récent au plus ancien."""
    return projets.historique(project_id, limite)
