"""Base de données de test : SQLite temporaire, migrée puis initialisée avec la base V1."""

import os
import tempfile

import pytest

_dossier = tempfile.mkdtemp(prefix="simtraction-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_dossier, "tests.db").replace("\\", "/")
os.environ["AUTO_IMPORT_V1"] = "true"


@pytest.fixture(scope="session", autouse=True)
def base_de_test():
    from app.db.migrations import initialiser_base

    initialiser_base()
    yield
