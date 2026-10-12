"""
Non-régression : le moteur Python doit reproduire le moteur V1 à 0,05 % près.
Nécessite Node.js (moteur V1). Les projets 25 kV sont marqués `slow` :
    pytest                      # projets 3 kV
    pytest -m slow              # projets 25 kV (plusieurs minutes)
"""

import shutil

import pytest

from tests.validation_v1.compare import TOLERANCE, valider, valider_etude

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js requis pour le moteur V1")

PROJETS_CC = [
    "Ain_Sebaa_2_Kenitra",
    "Ain_Sebaa_2_Kenitra_S_Actuelle",
    "Aourdou",
    "Bouskoura_2_Aeroport",
    "Casa_Port_2_Ain_Sebaa_2",
    "Casa_Port_2_Casa_Voyageurs_2",
    "Casa_Port_Casa_Port_2",
    "Casa_Voyageurs_2_Ain_Sebaa_2",
    "Casa_Voyageurs_2_Bouskoura_2",
    "Elainaoui",
    "Examine_ONCF",
    "Ouajar",
]
PROJETS_AC = [
    "Exemple_1_25_kV_ligne_nouvelle_A_D_150_km",
    "Exemple_2_25_kV_ligne_nouvelle_A_D_150_km",
]


def _assert_ecarts(ecarts):
    ko = [e for e in ecarts if e[0] > TOLERANCE]
    assert not ko, "\n".join(f"{nom}: V1={a} Py={b} ({e * 100:.3g} %)" for e, nom, a, b in ko[:10])


@pytest.mark.parametrize("projet", PROJETS_CC)
def test_cc3000_identique_a_v1(projet):
    _assert_ecarts(valider(projet, dt=5.0)[1])


@pytest.mark.slow
@pytest.mark.parametrize("projet", PROJETS_AC)
def test_ac25_identique_a_v1(projet):
    _assert_ecarts(valider(projet, dt=5.0)[1])


# Étude complète (normale + N-1 + séries) face au worker V1
@pytest.mark.parametrize("projet", ["Aourdou", "Casa_Voyageurs_2_Bouskoura_2", "Casa_Port_2_Casa_Voyageurs_2"])
def test_etude_n1_cc3000_identique_a_v1(projet):
    _assert_ecarts(valider_etude(projet, dt=5.0))


@pytest.mark.slow
@pytest.mark.parametrize("projet", PROJETS_AC)
def test_etude_n1_ac25_identique_a_v1(projet):
    _assert_ecarts(valider_etude(projet, dt=5.0))
