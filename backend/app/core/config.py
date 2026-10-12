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
    # Base de données V1 (dossier BDD en CSV), source des projets tant que PostgreSQL n'est pas branché
    v1_bdd_dir: Path = RACINE_DEPOT / "SimTraction_V1" / "BDD"
    # Nombre de simulations exécutées en parallèle par le serveur
    simulation_workers: int = 2

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
