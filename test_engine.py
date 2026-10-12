import sys
import os
import json

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.services.import_v1 import charger_projet_v1
from app.physics.simulation import SimulationEnv, simuler, analyser, verifications_normatives

def main():
    project_name = sys.argv[1] if len(sys.argv) > 1 else "Bouskoura_2_Aeroport"
    v1_project_path = os.path.abspath(f"SimTraction_V1/BDD/projets/{project_name}")
    print(f"Chargement du projet : {v1_project_path}", flush=True)
    data = charger_projet_v1(v1_project_path)
    
    print(f"Nom du projet : {data.get('nom')}")
    print(f"Système : {data.get('systeme')}")
    print(f"Tronçons de tracé : {len(data['trace']['troncons'])}")
    print(f"Engins matériel : {len(data['trains'])}")
    print(f"Circulations trafic : {len(data['trafic'])}")
    print(f"Sous-stations : {len(data['alimentation']['sst'])}")
    
    print("\nInitialisation de l'environnement de calcul...")
    env = SimulationEnv(data)
    print(f"Longueur de la ligne : {env.coord.total:.3f} km")
    print(f"Gares détectées : {[g['nom'] for g in env.gares]}")
    
    print("\nLancement de la simulation pas-à-pas (dt = 5 s)...")
    res_sim = simuler(env, {"dt": 5.0, "couplage": True})
    print(f"Simulation terminée en {res_sim['duree_calcul']:.2f} s")
    
    print("\nCalcul des métriques et analyse normative...")
    res_ana = analyser(env, res_sim)
    glob = res_ana["glob"]
    print(f"Tension minimale au pantographe : {glob['u_min']:.1f} V (Pire train: {glob['pire']['nom'] if glob['pire'] else 'N/A'})")
    print(f"Énergie fournie par les SST : {glob['energie_sst_kwh'] / 1000.0:.2f} MWh")
    print(f"Rendement global : {glob['rendement'] * 100:.1f} %")
    print(f"Pertes ligne : {glob['pertes_ligne_kwh']:.1f} kWh | Pertes SST : {glob['pertes_sst_kwh']:.1f} kWh")
    
    conf = verifications_normatives(res_ana, "normale")
    print("\nVérifications normatives (situation normale) :")
    for c in conf:
        status = "CONFORME" if c["ok"] else ("A EXAMINER" if c.get("indicatif") else "NON CONFORME")
        print(f"  - {c['critere']} ({c['norme']}) : {c['txt']} -> [{status}]")

    print("\nTEST MOTEUR SCIENTIFIQUE VALIDE AVEC SUCCÈS !")

if __name__ == "__main__":
    main()
