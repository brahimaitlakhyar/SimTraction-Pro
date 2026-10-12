"""
Solveur électrique pour les réseaux de traction 3 kV continu (CC).
- Ligne à plusieurs voies : caténaires séparées, rails communs couplés avec conductance de fuite au sol (G_re).
- Postes de mise en parallèle (PS) reliant les voies.
- Sous-stations à groupes transformateur-redresseur à diodes (U0, R_int, conduction unidirectionnelle).
- Résolution nodale par matrice bande (SciPy solve_banded ou algorithme direct O(N·W²)).
"""

import math
from typing import List, Dict, Any, Optional
import numpy as np
from scipy import linalg


class BandR:
    """Matrice bande réelle sans pivotage (adaptée aux matrices nodales à diagonale dominante)."""

    def __init__(self, n: int, w: int):
        self.n = n
        self.w = w
        self.W = 2 * w + 1
        self.a = np.zeros((n, self.W), dtype=np.float64)

    def add(self, i: int, j: int, v: float):
        self.a[i, j - i + self.w] += v

    def solve(self, b: np.ndarray) -> np.ndarray:
        n = self.n
        w = self.w
        W = self.W
        a = self.a
        b_res = np.array(b, dtype=np.float64, copy=True)

        for k in range(n):
            piv = a[k, w]
            if abs(piv) < 1e-14:
                piv = 1e-14
                a[k, w] = 1e-14
            iend = min(n - 1, k + w)
            for i in range(k + 1, iend + 1):
                ik = k - i + w
                f = a[i, ik] / piv
                if f == 0.0:
                    continue
                a[i, ik] = f
                jend = min(n - 1, k + w)
                for j in range(k + 1, jend + 1):
                    a[i, j - i + w] -= f * a[k, j - k + w]
                b_res[i] -= f * b_res[k]

        for k in range(n - 1, -1, -1):
            s = b_res[k]
            jend2 = min(n - 1, k + w)
            for j in range(k + 1, jend2 + 1):
                s -= a[k, j - k + w] * b_res[j]
            b_res[k] = s / a[k, w]

        return b_res


def unique_positions(points: List[float], tol: float = 1e-3) -> List[float]:
    """Trie et fusionne les positions proches à la tolérance tol."""
    sorted_pts = sorted(points)
    out: List[float] = []
    for p in sorted_pts:
        if not out or (p - out[-1]) > tol:
            out.append(p)
    return out


def pos_index(xs: List[float], x: float) -> int:
    """Trouve l'indice de x dans la liste triée xs."""
    lo = 0
    hi = len(xs) - 1
    while lo < hi:
        mid = (lo + hi) >> 1
        if xs[mid] < x - 1e-6:
            lo = mid + 1
        else:
            hi = mid
    if lo > 0 and abs(xs[lo - 1] - x) < abs(xs[lo] - x):
        lo -= 1
    return lo


def limite_p(p_kw: float, u_v: float, normes: Dict[str, Any], kp: float = 1.0) -> float:
    """Limitation de puissance des engins en sous-tension (EN 50388-1)."""
    u_lim_bas = float(normes.get("u_lim_bas", 1000.0) or 1000.0)
    u_lim_haut = float(normes.get("u_lim_haut", 2000.0) or 2000.0)
    u_max_recup = float(normes.get("u_max_recup", 3800.0) or 3800.0)

    if kp and kp < 1.0 and p_kw > 0:
        return p_kw * min(1.0, limite_p(1.0, u_v, normes) / max(kp, 1e-3))

    if p_kw > 0:
        if u_v <= u_lim_bas:
            return 0.0
        if u_v < u_lim_haut:
            return p_kw * (u_v - u_lim_bas) / (u_lim_haut - u_lim_bas)
        return p_kw

    if p_kw < 0:
        if u_v >= u_max_recup + 200.0:
            return 0.0
        if u_v > u_max_recup:
            return p_kw * (u_max_recup + 200.0 - u_v) / 200.0

    return p_kw


def resoudre_cc(cfg: Dict[str, Any], charges: List[Dict[str, Any]], u_init: Optional[Dict[int, float]] = None) -> Dict[str, Any]:
    """Résolution du réseau 3 kV continu par méthode nodale itérative."""
    nv = int(cfg.get("nv", 2))
    normes = cfg.get("normes", {})
    rf = float(cfg.get("r_feeder", 0.005) or 0.005)
    r_cat = float(cfg.get("r_cat", 0.05) or 0.05)
    r_rail = float(cfg.get("r_rail", 0.015) or 0.015)
    g_re = float(cfg.get("g_re", 0.2) or 0.2)

    all_sst = cfg.get("sst", [])
    active_sst = [s for s in all_sst if s.get("actif")]

    if not active_sst:
        # Ligne non alimentée
        res_zero = {
            "u": {c["id"]: 0.0 for c in charges},
            "i": {c["id"]: 0.0 for c in charges},
            "p": {c["id"]: 0.0 for c in charges},
            "vrail": {c["id"]: 0.0 for c in charges},
            "sst_i": [0.0] * len(all_sst),
            "sst_p": [0.0] * len(all_sst),
            "sst_u": [0.0] * len(all_sst),
            "fd_g": [0.0] * len(all_sst),
            "fd_d": [0.0] * len(all_sst),
            "pertes_ligne": 0.0,
            "pertes_sst": 0.0,
            "rheostat": 0.0,
            "iter": 0,
        }
        return res_zero

    postes_ps = [p for p in cfg.get("postes", []) if p.get("type") in ("PS", "SSP")]
    pts = [float(cfg["x_min"]), float(cfg["x_max"])]
    for s in active_sst:
        pts.append(float(s["x"]))
    for p in postes_ps:
        pts.append(float(p["x"]))
    for c in charges:
        pts.append(float(c["x"]))

    xs = unique_positions(pts, tol=1e-3)
    m = len(xs)

    has_bus = [-1] * m
    for j, s in enumerate(active_sst):
        has_bus[pos_index(xs, float(s["x"]))] = j

    base = [0] * (m + 1)
    n = 0
    w = 0
    for i in range(m):
        base[i] = n
        n += nv + 1 + (1 if has_bus[i] >= 0 else 0)
    base[m] = n

    for i in range(m - 1):
        w = max(w, base[i + 2] - 1 - base[i])
    w = max(w, nv + 2)

    def cat(node_i: int, v_voie: int) -> int:
        return base[node_i] + v_voie

    def rail(node_i: int) -> int:
        return base[node_i] + nv

    def bus(node_i: int) -> int:
        return base[node_i] + nv + 1

    rre = r_rail / nv
    ixc = [pos_index(xs, float(c["x"])) for c in charges]
    ixs = [pos_index(xs, float(s["x"])) for s in active_sst]
    diode = [True] * len(active_sst)

    un_nom = float(normes.get("un", 3000.0) or 3000.0)
    u_train = [(u_init.get(c["id"]) if u_init and c["id"] in u_init else un_nom) for c in charges]
    itr = np.zeros(len(charges), dtype=np.float64)
    isst = np.zeros(len(active_sst), dtype=np.float64)

    def build_system():
        A = BandR(n, w)

        def g_elem(a_node: int, b_node: int, conductance: float):
            A.add(a_node, a_node, conductance)
            A.add(b_node, b_node, conductance)
            A.add(a_node, b_node, -conductance)
            A.add(b_node, a_node, -conductance)

        # Segments de ligne
        for idx in range(m - 1):
            dx = max(xs[idx + 1] - xs[idx], 1e-4)
            for v_idx in range(nv):
                g_elem(cat(idx, v_idx), cat(idx + 1, v_idx), 1.0 / (r_cat * dx))
            g_elem(rail(idx), rail(idx + 1), 1.0 / (rre * dx))

        # Fuites rail-sol
        for idx in range(m):
            l_len = (xs[idx] - xs[idx - 1]) if idx > 0 else 0.0
            r_len = (xs[idx + 1] - xs[idx]) if idx < m - 1 else 0.0
            A.add(rail(idx), rail(idx), g_re * max((l_len + r_len) / 2.0, 0.05))

        # Postes de mise en parallèle (PS)
        for p in postes_ps:
            k_node = pos_index(xs, float(p["x"]))
            for v_idx in range(1, nv):
                g_elem(cat(k_node, 0), cat(k_node, v_idx), 1000.0)

        # Raccordement sous-station caténaires
        for j_sst, s in enumerate(active_sst):
            k_node = ixs[j_sst]
            for v_idx in range(nv):
                g_elem(bus(k_node), cat(k_node, v_idx), 1.0 / rf)

        return A, g_elem

    # Boucle de point fixe (Newton / relaxation)
    maxit = 40
    it_count = 0
    v_pot = np.zeros(n, dtype=np.float64)

    for it_count in range(maxit):
        A, g_elem = build_system()
        b_vec = np.zeros(n, dtype=np.float64)

        for j_sst, s in enumerate(active_sst):
            if not diode[j_sst]:
                continue
            k_node = ixs[j_sst]
            r_int = max(float(s.get("r_int", 0.05) or 0.05), 1e-4)
            gi = 1.0 / r_int
            u0 = float(s.get("u0", 3600.0) or 3600.0)
            g_elem(bus(k_node), rail(k_node), gi)
            b_vec[bus(k_node)] += u0 * gi
            b_vec[rail(k_node)] -= u0 * gi

        for c_idx, ch in enumerate(charges):
            p = limite_p(float(ch["p_kw"]), max(u_train[c_idx], 100.0), normes, float(ch.get("kp", 1.0)))
            itr[c_idx] = p * 1000.0 / max(u_train[c_idx], 100.0)
            k_node = ixc[c_idx]
            v_voie = min(max(int(ch.get("voie", 1)), 1), nv) - 1
            b_vec[cat(k_node, v_voie)] -= itr[c_idx]
            b_vec[rail(k_node)] += itr[c_idx]

        v_pot = A.solve(b_vec)

        # Mise à jour de l'état des diodes
        changed = False
        for j_sst, s in enumerate(active_sst):
            k_node = ixs[j_sst]
            du = v_pot[bus(k_node)] - v_pot[rail(k_node)]
            r_int = max(float(s.get("r_int", 0.05) or 0.05), 1e-4)
            u0 = float(s.get("u0", 3600.0) or 3600.0)

            if diode[j_sst]:
                cur = (u0 - du) / r_int
                if cur < -1e-6:
                    diode[j_sst] = False
                    changed = True
                    isst[j_sst] = 0.0
                else:
                    isst[j_sst] = cur
            else:
                if du < u0 - 1e-6:
                    diode[j_sst] = True
                    changed = True
                isst[j_sst] = 0.0

        # Erreur sur les tensions trains
        err = 0.0
        for c_idx, ch in enumerate(charges):
            k_node = ixc[c_idx]
            v_voie = min(max(int(ch.get("voie", 1)), 1), nv) - 1
            u_calc = v_pot[cat(k_node, v_voie)] - v_pot[rail(k_node)]
            err = max(err, abs(u_calc - u_train[c_idx]))
            u_train[c_idx] = (0.5 * u_train[c_idx] + 0.5 * u_calc) if it_count > 8 else u_calc

        if not changed and err < 0.5:
            break

    # Calcul des grandeurs de sortie
    res: Dict[str, Any] = {
        "u": {},
        "i": {},
        "p": {},
        "vrail": {},
        "sst_i": [0.0] * len(all_sst),
        "sst_p": [0.0] * len(all_sst),
        "sst_u": [float(s.get("u0", 3600.0) or 3600.0) for s in all_sst],
        "fd_g": [0.0] * len(all_sst),
        "fd_d": [0.0] * len(all_sst),
        "pertes_ligne": 0.0,
        "pertes_sst": 0.0,
        "rheostat": 0.0,
        "iter": it_count + 1,
    }

    pertes_sst = 0.0
    for j_sst, s in enumerate(active_sst):
        idx_global = all_sst.index(s)
        k_node = ixs[j_sst]
        res["sst_i"][idx_global] = float(isst[j_sst])
        u0 = float(s.get("u0", 3600.0) or 3600.0)
        r_int = max(float(s.get("r_int", 0.05) or 0.05), 1e-4)
        res["sst_p"][idx_global] = u0 * float(isst[j_sst]) / 1000.0
        res["sst_u"][idx_global] = float(v_pot[bus(k_node)] - v_pot[rail(k_node)])
        pertes_sst += float(isst[j_sst] * isst[j_sst] * r_int / 1000.0)

        gl = 0.0
        gr = 0.0
        for v_idx in range(nv):
            if k_node > 0:
                gl += (v_pot[cat(k_node, v_idx)] - v_pot[cat(k_node - 1, v_idx)]) / (r_cat * max(xs[k_node] - xs[k_node - 1], 1e-4))
            if k_node < m - 1:
                gr += (v_pot[cat(k_node, v_idx)] - v_pot[cat(k_node + 1, v_idx)]) / (r_cat * max(xs[k_node + 1] - xs[k_node], 1e-4))
        res["fd_g"][idx_global] = float(gl)
        res["fd_d"][idx_global] = float(gr)

    res["pertes_sst"] = pertes_sst

    for c_idx, ch in enumerate(charges):
        k_node = ixc[c_idx]
        v_voie = min(max(int(ch.get("voie", 1)), 1), nv) - 1
        uu = max(0.0, float(v_pot[cat(k_node, v_voie)] - v_pot[rail(k_node)]))
        c_id = ch["id"]
        res["u"][c_id] = uu
        res["i"][c_id] = float(itr[c_idx])
        p_absorbee = uu * float(itr[c_idx]) / 1000.0
        res["p"][c_id] = p_absorbee
        res["vrail"][c_id] = float(v_pot[rail(k_node)])

        p_dem = float(ch["p_kw"])
        if p_dem < 0:
            res["rheostat"] += max(0.0, -p_dem + p_absorbee)

    # Pertes Joule de ligne
    pl = 0.0
    for idx in range(m - 1):
        dx = max(xs[idx + 1] - xs[idx], 1e-4)
        for v_idx in range(nv):
            d_u = v_pot[cat(idx + 1, v_idx)] - v_pot[cat(idx, v_idx)]
            pl += d_u * d_u / (r_cat * dx)
        d_r = v_pot[rail(idx + 1)] - v_pot[rail(idx)]
        pl += d_r * d_r / (rre * dx)
    res["pertes_ligne"] = float(pl / 1000.0)

    return res
