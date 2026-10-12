"""
Normes et seuils normatifs applicables aux études de puissance de traction ferroviaire.
- EN 50163 : Tensions d'alimentation des réseaux de traction (Umin2, Umin1, Un, Umax1, Umax2)
- EN 50388-1 : Tension moyenne utile (TMU / Umoy) et critères de coordination
- EN 50122-1 : Potentiel du rail / tensions de contact admissibles
- EN 50160 : Taux de déséquilibre inverse admissible sur le réseau HT
"""

from typing import Dict, Any, Optional

DEFAULT_STANDARDS: Dict[str, Dict[str, Any]] = {
    "cc3000": {
        "un": 3000.0,
        "umin2": 2000.0,
        "umin1": 2000.0,
        "umax1": 3600.0,
        "umax2": 3900.0,
        "umoy_zone": 2700.0,
        "umoy_train": 2600.0,
        "umoy_zone_degrade": 2600.0,
        "u_lim_haut": 2000.0,
        "u_lim_bas": 1000.0,
        "u_max_recup": 3800.0,
        "v_rail_max": 120.0,
        "desequilibre_max_pct": None,
    },
    "ac25": {
        "un": 25000.0,
        "umin2": 17500.0,
        "umin1": 19000.0,
        "umax1": 27500.0,
        "umax2": 29000.0,
        "umoy_zone": 22000.0,
        "umoy_train": 21000.0,
        "umoy_zone_degrade": 21000.0,
        "u_lim_haut": 19000.0,
        "u_lim_bas": 17500.0,
        "u_max_recup": 29000.0,
        "v_rail_max": None,
        "desequilibre_max_pct": 2.0,
    }
}


def get_system_family(system: str) -> str:
    """Retourne la famille 'cc3000' ou 'ac25'."""
    return "cc3000" if system == "cc3000" else "ac25"


def merge_standards(system: str, custom_norms: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fusionne les seuils par défaut de la norme avec les réglages spécifiques du projet."""
    fam = get_system_family(system)
    norms = dict(DEFAULT_STANDARDS[fam])
    if custom_norms:
        for k, v in custom_norms.items():
            if v is not None and v != "":
                try:
                    norms[k] = float(v)
                except (ValueError, TypeError):
                    norms[k] = v
    return norms
