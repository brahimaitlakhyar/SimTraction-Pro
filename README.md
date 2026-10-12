# SimTraction Pro

**Plateforme professionnelle d'étude de puissance ferroviaire**

SimTraction Pro est un logiciel full-stack de simulation et dimensionnement des réseaux électriques de traction ferroviaire (DC 1,5 kV / 3 kV, AC 25 kV 1×25, AC 25 kV 2×25 BT/AT), compatible avec les normes EN 50388, EN 50633, NF EN 50163 et IEC 60850.

---

## Architecture

`
SimTraction Pro
├── backend/          # API FastAPI + moteur de calcul Python
│   ├── app/
│   │   ├── main.py           # Point d'entrée FastAPI
│   │   ├── api/              # Routeurs REST
│   │   ├── physics/          # Moteur électrotechnique (noyau de calcul)
│   │   ├── models/           # Schémas Pydantic
│   │   └── services/         # Services (import V1, BDD, export)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # Interface React + TypeScript + Vite
│   ├── src/
│   │   ├── pages/            # Pages de l'application
│   │   ├── components/       # Composants réutilisables
│   │   ├── api/              # Client API REST
│   │   └── store/            # Gestion d'état (Zustand)
│   ├── Dockerfile
│   └── package.json
├── SimTraction_V1/   # Version originale (référence)
├── docker-compose.yml
└── README.md
`

## Fonctionnalités

- **Cinématique de marche** – Simulation des régimes de traction/freinage avec profils de vitesse
- **Réseau DC** – Calcul de chute de tension, bilan de puissance, critère N-1
- **Réseau AC 1×25 / 2×25 BT/AT** – Répartition de courant, compensation, mutuelle
- **Dimensionnement automatique** – Sélection des SST, câblage AT, validation normative
- **Analyse KPI** – Tension minimale, courant max, facteur de charge, énergie récupérée
- **Rapport PDF/Excel** – Export automatique des résultats et courbes

## Installation rapide (Docker)

`ash
# Cloner le dépôt
git clone https://github.com/BrahimAitLakhyar/SimTraction-Pro.git
cd SimTraction-Pro

# Copier et configurer les variables d'environnement
cp .env.example .env

# Démarrer tous les services
docker compose up --build
`

Application disponible sur : http://localhost:3000

## Développement local

### Backend (FastAPI)

`ash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
`

API Swagger : http://localhost:8000/docs

### Frontend (React + Vite)

`ash
cd frontend
npm install
npm run dev
`

Frontend : http://localhost:5173

## Variables d'environnement

Copier .env.example en .env et configurer :

| Variable | Description | Défaut |
|---|---|---|
| DATABASE_URL | URL PostgreSQL | sqlite:///./simtraction.db |
| REDIS_URL | URL Redis (file de tâches) | edis://localhost:6379 |
| SECRET_KEY | Clé JWT | à générer |
| CORS_ORIGINS | Origines CORS autorisées | http://localhost:5173 |

## Stack technologique

| Couche | Technologie |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Celery |
| Frontend | React 18, TypeScript, Vite, Recharts |
| Base de données | PostgreSQL 16 / SQLite (dev) |
| Cache/Queue | Redis 7 |
| Reverse Proxy | Nginx |
| Containerisation | Docker, Docker Compose |

## Référence scientifique

- EN 50388:2012 – Alimentation en énergie et matériel roulant
- EN 50633:2020 – Alimentation électrique des systèmes de transport 2×25 kV
- NF EN 50163 – Tensions d'alimentation des systèmes de traction
- IEC 60850 – Tensions d'alimentation

## Auteur

**Brahim Ait Lakhyar** – aitlakhyarbrahim@gmail.com

---

*Basé sur SimTraction V1 – évolution vers une plateforme professionnelle déployable en ligne.*
