"""
Noyau de calcul physique et électrotechnique de SimTraction Pro.
"""

from .standards import merge_standards, get_system_family, DEFAULT_STANDARDS
from .train import Train
from .track import Coord, Parcours, extract_gares
from .kinematics import Marche, marche_isolee
from .solver_dc import resoudre_cc, limite_p
from .solver_ac import resoudre_ac
from .simulation import SimulationEnv, build_network_configuration, build_configuration_n1, simuler, analyser, verifications_normatives
from .dimensioning import dimensionner, comparer_variantes

__all__ = [
    "Train",
    "Coord",
    "Parcours",
    "extract_gares",
    "Marche",
    "marche_isolee",
    "resoudre_cc",
    "resoudre_ac",
    "limite_p",
    "SimulationEnv",
    "build_network_configuration",
    "build_configuration_n1",
    "simuler",
    "analyser",
    "verifications_normatives",
    "dimensionner",
    "comparer_variantes",
    "merge_standards",
    "get_system_family",
    "DEFAULT_STANDARDS",
]
