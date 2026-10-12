"""Environnement Alembic : URL de la base lue dans la configuration de l'application (DATABASE_URL)."""

from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings
from app.db import get_engine
from app.db.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configurer_journal", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Génère le SQL sans connexion (alembic upgrade head --sql)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # ALTER TABLE compatibles SQLite
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
