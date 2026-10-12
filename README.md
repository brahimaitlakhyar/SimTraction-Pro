# SimTraction Pro

**Plateforme professionnelle d'étude de puissance ferroviaire**

SimTraction Pro est un logiciel full-stack de simulation et dimensionnement des réseaux électriques de traction ferroviaire (DC 3 kV, AC 25 kV 1×25, AC 25 kV 2×25 BT/AT), compatible avec les normes EN 50388, EN 50633, NF EN 50163 et IEC 60850.

---

## Architecture

```
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
```

## Fonctionnalités

- **Cinématique de marche** – Simulation des régimes de traction/freinage avec profils de vitesse
- **Réseau DC** – Calcul de chute de tension, bilan de puissance, critère N-1
- **Réseau AC 1×25 / 2×25 BT/AT** – Répartition de courant, compensation, mutuelle
- **Dimensionnement automatique** – Sélection des SST, câblage AT, validation normative
- **Analyse KPI** – Tension minimale, courant max, facteur de charge, énergie récupérée
- **Rapport PDF/Excel** – Export automatique des résultats et courbes

## Installation rapide (Docker)

```bash
# Cloner le dépôt
git clone https://github.com/BrahimAitLakhyar/SimTraction-Pro.git
cd SimTraction-Pro

# Copier et configurer les variables d'environnement
cp .env.example .env

# Démarrer tous les services
docker compose up --build
```

Application disponible sur : http://localhost:3000

## Développement local

### Backend (FastAPI)

Python 3.12 recommandé.

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

API Swagger : http://localhost:8000/docs

Les projets sont lus dans `SimTraction_V1/BDD` (variable `V1_BDD_DIR`) en attendant la base PostgreSQL.

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/v1/projects/` | Liste des projets |
| GET | `/api/v1/projects/{id}` | Projet complet (tracé, matériel, trafic, alimentation) |
| POST | `/api/v1/simulation/run` | Lance une étude : `{project_id, dt, couplage, n1, alimentation?}` (alimentation proposée vérifiée sans être enregistrée) |
| GET | `/api/v1/simulation/status/{task_id}` | Progression (0 → 100 %) |
| GET | `/api/v1/simulation/result/{task_id}` | Résultats : analyse, conformité, N-1, séries |
| GET | `/api/v1/dimensioning/parametres/{id}` | Paramètres de dimensionnement par défaut (projet, puis `reglages.csv`) |
| POST | `/api/v1/dimensioning/run` | Dimensionnement : `{project_id, mode: "dimensionner" \| "comparer", parametres}` |
| GET | `/api/v1/dimensioning/status/{task_id}` | Progression et journal de recherche |
| GET | `/api/v1/dimensioning/result/{task_id}` | Sous-stations, postes, calibres, marges (ou variantes comparées) |
| GET | `/api/v1/materials/` | Bibliothèque du matériel roulant |
| GET | `/api/v1/references/normes` | Seuils normatifs (`?systeme=cc3000` ou `ac25`) |
| GET | `/api/v1/references/sites-ht` | Postes HT de raccordement |

### Tests

```bash
cd backend
pytest              # API + non-régression contre V1 sur les projets 3 kV (Node.js requis)
pytest -m slow      # projets 25 kV (plusieurs minutes)
```

La non-régression exécute le moteur JavaScript de SimTraction V1 sous Node
(`tests/validation_v1/v1_run.js`) et vérifie que le moteur Python donne les mêmes résultats à 0,05 % près :
simulation, situations N-1, textes de conformité, dimensionnement et comparaison des puissances unitaires
(solution, calibres, marges et journal de recherche).

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Frontend : http://localhost:5173

## Variables d'environnement

Copier .env.example en .env et configurer :

| Variable | Description | Défaut |
|---|---|---|
| DATABASE_URL | URL PostgreSQL | sqlite:///./simtraction.db |
| REDIS_URL | URL Redis (file de tâches) | redis://localhost:6379 |
| SECRET_KEY | Clé JWT | à générer |
| CORS_ORIGINS | Origines CORS autorisées | http://localhost:5173 |

## Stack technologique

| Couche | Technologie |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Celery |
| Frontend | React 19, TypeScript, Vite, Apache ECharts |
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
