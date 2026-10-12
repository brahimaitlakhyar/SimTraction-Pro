"""
SimTraction Pro - Backend FastAPI
Point d'entrée principal de l'API REST.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

from app.api import projects, simulation, materials, substations, health

app = FastAPI(
    title="SimTraction Pro API",
    description="API REST pour la simulation et le dimensionnement des réseaux de traction ferroviaire",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────
cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(simulation.router, prefix="/api/v1/simulation", tags=["Simulation"])
app.include_router(materials.router, prefix="/api/v1/materials", tags=["Materials"])
app.include_router(substations.router, prefix="/api/v1/substations", tags=["Substations"])


@app.get("/")
async def root():
    return {"message": "SimTraction Pro API v2.0", "docs": "/docs"}
