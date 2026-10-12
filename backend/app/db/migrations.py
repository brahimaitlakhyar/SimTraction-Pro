"""Mise à jour du schéma (Alembic) et initialisation de la base au démarrage."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings

log = logging.getLogger("simtraction")
BACKEND = Path(__file__).resolve().parents[2]


def migrer():
    """alembic upgrade head."""
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["configurer_journal"] = False  # ne pas écraser la configuration des journaux d'uvicorn
    command.upgrade(cfg, "head")


def initialiser_base():
    """Schéma à jour, puis import de la base V1 si la base est vide (premier démarrage)."""
    from app.services.import_bdd_v1 import importer_bdd_v1
    from app.services.projets import base_vide

    migrer()
    reglages = get_settings()
    if reglages.auto_import_v1 and base_vide() and (Path(reglages.v1_bdd_dir) / "projets").is_dir():
        r = importer_bdd_v1(Path(reglages.v1_bdd_dir))
        log.warning("Base vide : %d projets V1 importés depuis %s", len(r["projets_importes"]), reglages.v1_bdd_dir)
