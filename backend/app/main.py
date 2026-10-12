"""
SimTraction Pro - Backend FastAPI
Point d'entrée principal de l'API REST.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dimensioning, health, materials, projects, references, simulation
from app.core.config import get_settings
from app.physics.noyaux import prechauffer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    prechauffer()  # compile les noyaux Numba au démarrage plutôt qu'au premier calcul
    yield


app = FastAPI(
    lifespan=lifespan,
    title="SimTraction Pro API",
    description="API REST pour la simulation et le dimensionnement des réseaux de traction ferroviaire",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(simulation.router, prefix="/api/v1/simulation", tags=["Simulation"])
app.include_router(dimensioning.router, prefix="/api/v1/dimensioning", tags=["Dimensioning"])
app.include_router(materials.router, prefix="/api/v1/materials", tags=["Materials"])
app.include_router(references.router, prefix="/api/v1/references", tags=["References"])


@app.get("/")
async def root():
    return {"message": "SimTraction Pro API v2.0", "docs": "/docs"}
