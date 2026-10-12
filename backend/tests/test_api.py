"""Tests de l'API REST sur la base V1 réelle (14 projets)."""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.physics import SimulationEnv, analyser, simuler
from app.services.bdd_v1 import projet_pour_calcul

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_liste_projets():
    projets = client.get("/api/v1/projects/").json()
    assert len(projets) == 14
    p = next(x for x in projets if x["id"] == "Bouskoura_2_Aeroport")
    assert p["systeme"] == "cc3000"
    assert p["longueur_km"] == pytest.approx(12.329)
    assert (p["nb_trains"], p["nb_circulations"], p["nb_sst"], p["nb_postes"]) == (10, 5, 1, 0)


def test_projet_complet():
    P = client.get("/api/v1/projects/Exemple_2_25_kV_ligne_nouvelle_A_D_150_km").json()
    assert P["systeme"] == "ac2x25"
    assert len(P["alimentation"]["sst"]) == 3
    assert P["trace"]["troncons"]


@pytest.mark.parametrize("pid", ["inexistant", "..", "../parametres", "..%2Fparametres"])
def test_projet_introuvable_ou_hors_base(pid):
    # identifiants interprétés comme clés de base (aucun accès disque) : jamais de contenu renvoyé
    assert client.get(f"/api/v1/projects/{pid}").status_code in (404, 405)


def test_bibliotheques():
    assert len(client.get("/api/v1/materials/").json()) == 13
    normes = client.get("/api/v1/references/normes", params={"systeme": "ac25"}).json()
    assert {n["code"]: n["valeur"] for n in normes}["umin1"] == 19000
    assert len(client.get("/api/v1/references/sites-ht").json()) == 7


def _attendre(task_id: str, delai: float = 120.0):
    t0 = time.time()
    while time.time() - t0 < delai:
        st = client.get(f"/api/v1/simulation/status/{task_id}").json()
        if st["status"] in ("done", "error"):
            return st
        time.sleep(0.2)
    raise TimeoutError(task_id)


def test_etude_complete_avec_n1():
    pid = "Casa_Port_2_Casa_Voyageurs_2"  # 2 SST : un cas N-1 par sous-station
    r = client.post("/api/v1/simulation/run", json={"project_id": pid, "dt": 5, "n1": True})
    assert r.status_code == 202
    st = _attendre(r.json()["task_id"])
    assert st["status"] == "done", st.get("error")
    assert st["progress"] == 100

    res = client.get(f"/api/v1/simulation/result/{st['task_id']}").json()
    assert set(res) >= {"A", "conf", "n1", "series", "avert", "opts", "duree"}
    assert len(res["n1"]) == 2
    assert res["series"]["circ"] and res["series"]["sst"]

    # Même résultat que le moteur appelé directement
    env = SimulationEnv(projet_pour_calcul(pid))
    A = analyser(env, simuler(env, {"dt": 5, "couplage": True}))
    assert res["A"]["glob"]["u_min"] == pytest.approx(A["glob"]["u_min"])


def test_etude_projet_inexistant():
    assert client.post("/api/v1/simulation/run", json={"project_id": "inexistant"}).status_code == 404


def test_etude_parametres_invalides():
    assert client.post("/api/v1/simulation/run", json={"project_id": "Aourdou", "dt": 0}).status_code == 422
    assert client.post("/api/v1/simulation/run", json={"project_id": "Aourdou", "n1": "parfois"}).status_code == 422


def test_resultat_tache_inconnue():
    assert client.get("/api/v1/simulation/result/inconnue").status_code == 404


# ── Dimensionnement ──────────────────────────────────────────────────

def _attendre_dim(task_id: str, delai: float = 300.0):
    t0 = time.time()
    while time.time() - t0 < delai:
        st = client.get(f"/api/v1/dimensioning/status/{task_id}").json()
        if st["status"] in ("done", "error"):
            return st
        time.sleep(0.3)
    raise TimeoutError(task_id)


def test_parametres_dimensionnement():
    r = client.get("/api/v1/dimensioning/parametres/Aourdou").json()
    assert r["systeme"] == "cc3000"
    # valeurs vides du projet complétées par reglages.csv (dim.cc3000.*)
    assert r["parametres"]["pas_min_km"] == 8 and r["parametres"]["pas_max_km"] == 30
    assert r["parametres"]["puissances"] == "3000;4500;6000;9000;12000"
    assert r["variantes"] == [3000, 6000]


def test_dimensionnement_puis_verification():
    pid = "Casa_Voyageurs_2_Bouskoura_2"
    r = client.post("/api/v1/dimensioning/run", json={"project_id": pid, "parametres": {"n1": False}})
    assert r.status_code == 202
    st = _attendre_dim(r.json()["task_id"])
    assert st["status"] == "done", st.get("error")
    assert st["journal"] and "SST" in st["journal"][0]

    res = client.get(f"/api/v1/dimensioning/result/{st['task_id']}").json()
    sol = res["resultat"]
    assert sol["ok"] and sol["n"] == len(sol["sst"]) == len(sol["besoins"])
    assert all(b["choix"] for b in sol["besoins"])

    # La solution proposée, vérifiée par une étude complète sans modifier le projet
    r = client.post("/api/v1/simulation/run", json={"project_id": pid, "n1": False,
                                                    "alimentation": {"sst": sol["sst"], "postes": sol["postes"]}})
    st = _attendre(r.json()["task_id"])
    assert st["status"] == "done", st.get("error")
    etude = client.get(f"/api/v1/simulation/result/{st['task_id']}").json()
    assert [s["nom"] for s in etude["A"]["sst"]] == [s["nom"] for s in sol["sst"]]
    assert all(c["ok"] or c.get("indicatif") for c in etude["conf"])
    assert client.get(f"/api/v1/projects/{pid}").json()["alimentation"]["sst"] != sol["sst"]


def test_comparaison_sans_variante():
    r = client.post("/api/v1/dimensioning/run",
                    json={"project_id": "Aourdou", "mode": "comparer", "parametres": {"variantes": "aucune"}})
    st = _attendre_dim(r.json()["task_id"])
    assert st["status"] == "error" and "puissance unitaire" in st["error"]


def test_types_de_taches_separes():
    r = client.post("/api/v1/dimensioning/run", json={"project_id": "inexistant"})
    assert r.status_code == 404
    t = client.post("/api/v1/simulation/run", json={"project_id": "Casa_Port_2_Ain_Sebaa_2", "n1": False}).json()
    assert client.get(f"/api/v1/dimensioning/status/{t['task_id']}").status_code == 404
