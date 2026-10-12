"""Configuration de l'application (variables d'environnement / fichier .env)."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

RACINE_DEPOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    # Base de données : PostgreSQL en production (postgresql+psycopg://…), SQLite par défaut en développement
    database_url: str = f"sqlite:///{(RACINE_DEPOT / 'backend' / 'simtraction.db').as_posix()}"
    # Base V1 (dossier BDD en CSV) : importée automatiquement au premier démarrage si la base est vide
    v1_bdd_dir: Path = RACINE_DEPOT / "SimTraction_V1" / "BDD"
    auto_import_v1: bool = True
    # Nombre de simulations exécutées en parallèle par le serveur
    simulation_workers: int = 2

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
