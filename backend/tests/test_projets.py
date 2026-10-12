"""Projets en base : import V1 sans perte, édition avec verrou optimiste, variantes, historique des calculs."""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.physics import SimulationEnv, analyser, simuler
from app.services import bdd_v1, calculs, projets

client = TestClient(app)
PROJETS_V1 = [p["id"] for p in bdd_v1.lister_projets()]


def _sans_vides(x):
    """Une case vide des CSV V1 ('') équivaut à une valeur absente pour le moteur."""
    if isinstance(x, dict):
        return {k: _sans_vides(v) for k, v in x.items() if not (v == "" and k not in ("gare", "nom", "type", "depart", "arrets", "libelle", "en_service", "at"))}
    if isinstance(x, list):
        return [_sans_vides(v) for v in x]
    return x


@pytest.mark.parametrize("pid", PROJETS_V1)
def test_import_v1_sans_perte(pid):
    """Le projet relu en base est celui des CSV V1 (hors métadonnées de fichier)."""
    db = projets.projet_pour_calcul(pid)
    csv = bdd_v1.projet_pour_calcul(pid)
    for P in (db, csv):
        P.pop("modifie", None)
        P.pop("_dernier", None)
    assert _sans_vides(db) == _sans_vides(csv)


@pytest.mark.parametrize("pid", ["Bouskoura_2_Aeroport", "Exemple_2_25_kV_ligne_nouvelle_A_D_150_km"])
def test_calcul_identique_base_et_csv(pid):
    ga = analyser(e := SimulationEnv(projets.projet_pour_calcul(pid)), simuler(e, {"dt": 5.0}))["glob"]
    gb = analyser(f := SimulationEnv(bdd_v1.projet_pour_calcul(pid)), simuler(f, {"dt": 5.0}))["glob"]
    assert (ga["u_min"], ga["energie_sst_kwh"], ga["pertes_ligne_kwh"]) == (gb["u_min"], gb["energie_sst_kwh"], gb["pertes_ligne_kwh"])


def test_nouveau_projet_vierge():
    r = client.post("/api/v1/projects/", json={"nom": "Ligne d'essai é/à", "systeme": "ac2x25"})
    assert r.status_code == 201
    P = r.json()
    assert P["id"] == "Ligne_d_essai_e_a" and P["systeme"] == "ac2x25" and P["_meta"]["version"] == 1
    assert [t["gare"] for t in P["trace"]["troncons"]] == ["Gare A", "", "Gare B"]
    assert P["alimentation"]["ac"]["u0"] == 27500 and P["alimentation"]["sst"] == []
    # même nom : identifiant suivant libre
    assert client.post("/api/v1/projects/", json={"nom": "Ligne d'essai é/à"}).json()["id"] == "Ligne_d_essai_e_a_2"
    assert client.post("/api/v1/projects/", json={"nom": "X", "systeme": "dc1500"}).status_code == 422


def test_modification_et_verrou_optimiste():
    pid = client.post("/api/v1/projects/", json={"nom": "Edition"}).json()["id"]
    P = client.get(f"/api/v1/projects/{pid}").json()
    troncons = P["trace"]["troncons"] + [{"pk_ini": 30, "pk_fin": "31,5", "pente": "-2,5", "gare": "Gare C"}]

    r = client.put(f"/api/v1/projects/{pid}/trace", json={"version": 1, "donnees": troncons})
    assert r.status_code == 200
    P2 = r.json()
    assert P2["_meta"]["version"] == 2
    assert P2["trace"]["troncons"][-1] == {"pk_ini": 30, "pk_fin": 31.5, "pente": -2.5, "gare": "Gare C"}

    # modification concurrente sur une version périmée : refusée
    r = client.put(f"/api/v1/projects/{pid}/trace", json={"version": 1, "donnees": []})
    assert r.status_code == 409 and "version actuelle 2" in r.json()["detail"]

    assert client.put(f"/api/v1/projects/{pid}/trace", json={"version": 2, "donnees": [{"pk_ini": "abc"}]}).status_code == 422
    assert client.put(f"/api/v1/projects/{pid}/inconnue", json={"donnees": []}).status_code == 404

    r = client.put(f"/api/v1/projects/{pid}/informations", json={"version": 2, "donnees": {"nom": "Édition 2", "duree_s": 7200}})
    assert r.json()["nom"] == "Édition 2" and r.json()["duree_s"] == 7200 and r.json()["_meta"]["version"] == 3
    assert client.put(f"/api/v1/projects/{pid}/informations", json={"donnees": {"nom": ""}}).status_code == 422


def test_variante_et_suppression():
    r = client.post("/api/v1/projects/", json={"nom": "Variante Bouskoura", "copie_de": "Bouskoura_2_Aeroport"})
    assert r.status_code == 201
    pid = r.json()["id"]
    orig, var = projets.projet_pour_calcul("Bouskoura_2_Aeroport"), projets.projet_pour_calcul(pid)
    assert {k: v for k, v in var.items() if k not in ("id", "nom")} == {k: v for k, v in orig.items() if k not in ("id", "nom")}

    assert client.delete(f"/api/v1/projects/{pid}").status_code == 204
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}").status_code == 404
    assert client.post("/api/v1/projects/", json={"nom": "X", "copie_de": "inexistant"}).status_code == 404


def _attendre(task_id: str):
    for _ in range(600):
        st = client.get(f"/api/v1/simulation/status/{task_id}").json()
        if st["status"] in ("done", "error"):
            return st
        time.sleep(0.2)
    raise TimeoutError(task_id)


def test_solution_appliquee_puis_historique_conserve():
    pid = client.post("/api/v1/projects/", json={"nom": "Application", "copie_de": "Casa_Port_2_Casa_Voyageurs_2"}).json()["id"]
    P = client.get(f"/api/v1/projects/{pid}").json()
    sst = P["alimentation"]["sst"][:1]  # une seule sous-station conservée
    r = client.put(f"/api/v1/projects/{pid}/sous_stations", json={"version": P["_meta"]["version"], "donnees": sst})
    assert [s["nom"] for s in r.json()["alimentation"]["sst"]] == [sst[0]["nom"]]

    t = client.post("/api/v1/simulation/run", json={"project_id": pid, "n1": False}).json()
    st = _attendre(t["task_id"])
    assert st["status"] == "done"
    res = client.get(f"/api/v1/simulation/result/{t['task_id']}").json()
    assert [s["nom"] for s in res["A"]["sst"]] == [sst[0]["nom"]]

    # dernier calcul visible dans la liste des projets
    resume = next(p for p in client.get("/api/v1/projects/").json() if p["id"] == pid)
    assert resume["dernier_u_min"] == pytest.approx(res["A"]["glob"]["u_min"])

    # le serveur « oublie » ses tâches (redémarrage) : le calcul reste disponible depuis la base
    calculs._taches.clear()
    assert client.get(f"/api/v1/simulation/status/{t['task_id']}").json()["status"] == "done"
    assert client.get(f"/api/v1/simulation/result/{t['task_id']}").json()["A"]["glob"]["u_min"] == res["A"]["glob"]["u_min"]
    hist = client.get(f"/api/v1/projects/{pid}/historique").json()
    assert hist[0]["task_id"] == t["task_id"] and hist[0]["type"] == "etude" and hist[0]["status"] == "done"
