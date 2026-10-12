"""
Équivalents Python des conversions et arrondis JavaScript utilisés par SimTraction V1.
Indispensables pour reproduire exactement le dimensionnement V1 : Python arrondit au pair
(round(2.5) = 2) alors que Math.round arrondit vers +∞ (3), et toFixed arrondit au plus loin de 0.
"""

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def js_round(x: float) -> float:
    """Math.round : entier le plus proche, égalité vers +∞."""
    if not math.isfinite(x):
        return x
    f = math.floor(x)
    return float(f + 1 if x - f >= 0.5 else f)


def js_fixed(x: float, d: int) -> str:
    """Number.prototype.toFixed(d) (valeur binaire exacte, égalité au plus loin de zéro)."""
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        x = 0.0  # (-0).toFixed() donne « 0 »
    return str(Decimal(x).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def js_fixed_num(x: float, d: int) -> float:
    """+x.toFixed(d)."""
    return float(js_fixed(x, d))


def js_num(x: Any, defaut: Any) -> Any:
    """num() du moteur V1 : défaut si vide, null ou non numérique, sinon +x."""
    if x is None or x == "":
        return defaut
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return defaut if math.isnan(x) else float(x)
    try:
        v = float(str(x).strip()) if str(x).strip() else 0.0
    except ValueError:
        return defaut
    return defaut if math.isnan(v) else v


def js_str(x: float) -> str:
    """Conversion d'un nombre en chaîne comme JavaScript (8 → « 8 », 8.5 → « 8.5 »)."""
    x = float(x)
    if math.isfinite(x) and x.is_integer() and abs(x) < 1e21:
        return str(int(x))
    return repr(x)


def js_sign(x: float) -> float:
    return 0.0 if x == 0 else (1.0 if x > 0 else -1.0)
