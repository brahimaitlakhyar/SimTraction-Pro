"""
Modèle physique du matériel roulant ferroviaire (engins moteurs et rames).
- Résistance Davis (a + bv + cv²)
- Moteur série CC (RailPower, paramètres c2 et c3)
- Moteur moderne tabulé / triphasé (Fmax, Pmax, rendement, cos phi)
- Réduction de puissance en basse tension (EN 50388-1)
- Freinage électrique et régénération
"""

import math
from typing import Dict, Any, Optional

G_ACCEL = 9.81  # m/s²


class Train:
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        d = data or {}
        self.ref = d.get("ref", 0)
        self.nom = str(d.get("nom", "Engin"))
        self.type = str(d.get("type", "tabule"))  # 'serie_cc' ou 'tabule'
        self.masse_t = float(d.get("masse_t", 100.0) or 100.0)
        self.masse_dyn_t = float(d.get("masse_dyn_t", 0.0) or 0.0)
        if not self.masse_dyn_t:
            self.masse_dyn_t = 1.04 * self.masse_t

        self.longueur_m = float(d.get("longueur_m", 0.0) or 0.0)
        self.v_max = float(d.get("v_max", 160.0) or 160.0)  # km/h
        self.u_nom = float(d.get("u_nom", 3000.0) or 3000.0)  # V

        # Formule de Davis : R = A + B*v + C*v² (kN)
        self.davis_a = float(d.get("davis_a", 2.0) or 2.0)
        self.davis_b = float(d.get("davis_b", 0.02) or 0.02)
        self.davis_c = float(d.get("davis_c", 0.0004) or 0.0004)

        # Résistance de courbe
        self.coef_courbe = float(d.get("coef_courbe", 0.0) or 0.0)
        if not self.coef_courbe:
            self.coef_courbe = 4.67 * self.masse_t

        # Caractéristiques de traction
        self.f_max = float(d.get("f_max", 200.0) or 200.0)  # kN
        self.v1 = float(d.get("v1", 0.0) or 0.0)            # km/h (moteur série)
        self.p_max_kw = float(d.get("p_max_kw", 4000.0) or 4000.0)
        self.rendement = float(d.get("rendement", 0.85) or 0.85)
        self.p_aux_kw = float(d.get("p_aux_kw", 0.0) or 0.0)
        self.i_aux = float(d.get("i_aux", 0.0) or 0.0)      # A
        self.cos_phi = float(d.get("cos_phi", 0.98) or 0.98)

        # Paramètres moteur série CC (RailPower)
        self.c2_ohm = float(d.get("c2_ohm", 0.0) or 0.0)
        self.c3 = float(d.get("c3", 0.0) or 0.0)

        # Freinage électrique
        self.f_frein = float(d.get("f_frein", 100.0) or 100.0)  # kN
        self.p_frein_kw = float(d.get("p_frein_kw", 2000.0) or 2000.0)  # kW
        self.rendement_recup = float(d.get("rendement_recup", 0.0) or 0.0)  # 0 à 1
        self.decel_service = float(d.get("decel_service", 0.2) or 0.2)  # m/s²

    def resistance(self, v_kmh: float, tunnel: float = 0.0) -> float:
        """Résistance à l'avancement en kN (formule de Davis avec majoration tunnel)."""
        r = self.davis_a + self.davis_b * v_kmh + self.davis_c * v_kmh * v_kmh
        return r * (1.0 + (tunnel or 0.0))

    def force_pente(self, pente_permille: float) -> float:
        """Effort dû à la pente/rampe en kN. Rampe (> 0) = résistance positive."""
        return self.masse_t * G_ACCEL * (pente_permille or 0.0) / 1000.0

    def force_courbe(self, rayon_m: float) -> float:
        """Résistance de courbure en kN."""
        if rayon_m and rayon_m > 0:
            return self.coef_courbe / rayon_m
        return 0.0

    def effort_max(self, v_kmh: float, u_v: Optional[float] = None, kp: float = 1.0) -> float:
        """
        Effort maximal de traction disponible à la vitesse v_kmh sous la tension u_v (kN).
        kp : fraction de puissance autorisée par la tension (derating EN 50388).
        """
        if v_kmh >= self.v_max:
            return 0.0
        if kp is None:
            kp = 1.0

        if self.type == "serie_cc" and self.c3 > 0:
            u = u_v if u_v is not None else self.u_nom
            im = math.sqrt(self.f_max / self.c3)
            vt = max(1e-6, (u - self.c2_ohm * im) / (self.c3 * 1000.0 * im / 3.6))
            if v_kmh <= vt:
                f = self.f_max
            else:
                i = u / (self.c3 * 1000.0 * v_kmh / 3.6 + self.c2_ohm)
                f = self.c3 * i * i
            return f * kp

        # Moteur moderne tabulé : F_max borné par P_max
        fp = (self.p_max_kw * 3.6 / v_kmh) if v_kmh > 0.5 else float("inf")
        return min(self.f_max, fp) * kp

    def p_aux(self, u_v: Optional[float] = None) -> float:
        """Puissance des auxiliaires en kW."""
        if self.type == "serie_cc":
            u = u_v if u_v is not None else self.u_nom
            return u * self.i_aux / 1000.0
        return self.p_aux_kw or (self.i_aux * self.u_nom / 1000.0)

    def puissance_elec(self, f_kn: float, v_kmh: float, u_v: Optional[float] = None) -> float:
        """Puissance électrique absorbée au pantographe en kW pour un effort f >= 0."""
        aux = self.p_aux(u_v)
        if f_kn <= 0:
            return aux
        pm = f_kn * v_kmh / 3.6  # Puissance mécanique en kW
        if self.type == "serie_cc" and self.c3 > 0:
            im2 = f_kn / self.c3
            return pm + self.c2_ohm * im2 / 1000.0 + aux
        return pm / (self.rendement or 0.85) + aux

    def effort_frein_elec(self, v_kmh: float) -> float:
        """Effort maximal de freinage électrique récupérateur en kN."""
        if v_kmh <= 0.1 or self.f_frein <= 0:
            return 0.0
        if self.p_frein_kw > 0:
            return min(self.f_frein, self.p_frein_kw * 3.6 / v_kmh)
        return self.f_frein

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "nom": self.nom,
            "type": self.type,
            "masse_t": self.masse_t,
            "masse_dyn_t": self.masse_dyn_t,
            "longueur_m": self.longueur_m,
            "f_max": self.f_max,
            "v1": self.v1,
            "v_max": self.v_max,
            "p_max_kw": self.p_max_kw,
            "rendement": self.rendement,
            "p_aux_kw": self.p_aux_kw,
            "cos_phi": self.cos_phi,
            "u_nom": self.u_nom,
            "davis_a": self.davis_a,
            "davis_b": self.davis_b,
            "davis_c": self.davis_c,
            "coef_courbe": self.coef_courbe,
            "c2_ohm": self.c2_ohm,
            "c3": self.c3,
            "i_aux": self.i_aux,
            "f_frein": self.f_frein,
            "p_frein_kw": self.p_frein_kw,
            "rendement_recup": self.rendement_recup,
            "decel_service": self.decel_service,
        }
