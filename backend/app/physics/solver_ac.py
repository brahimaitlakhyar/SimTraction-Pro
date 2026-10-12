"""
Solveur électrique alternatif 25 kV 50 Hz (1×25 kV et 2×25 kV avec autotransformateurs).
- Analyse nodale complexe en matrice bande O(N·W²).
- Transformateurs de sous-station (Thévenin : impédance HT Scc + impédance transformateur Ucc).
- Système 2×25 kV : conducteurs caténaire (+25 kV), feeder (-25 kV), autotransformateurs (AT).
- Sections neutres aux sous-stations et aux postes de sectionnement (SP).
- Parallélisme des voies aux postes SSP.
- Charges à puissance constante S = P + j·Q avec limitation en sous-tension (EN 50388-1).
"""

import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from .noyaux import resoudre_bande_complexe
from .solver_dc import unique_positions, pos_index, limite_p


class BandC:
    """Matrice bande complexe sans pivotage pour les réseaux alternatifs."""

    def __init__(self, n: int, w: int):
        self.n = n
        self.w = w
        self.W = 2 * w + 1
        self.re = np.zeros((n, self.W), dtype=np.float64)
        self.im = np.zeros((n, self.W), dtype=np.float64)

    def copie(self) -> "BandC":
        c = BandC.__new__(BandC)
        c.n, c.w, c.W = self.n, self.w, self.W
        c.re = self.re.copy()
        c.im = self.im.copy()
        return c

    def add(self, i: int, j: int, vr: float, vi: float):
        k = j - i + self.w
        self.re[i, k] += vr
        self.im[i, k] += vi

    def solve(self, br: np.ndarray, bi: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        # Noyau compilé (noyaux.py), opérations identiques à l'élimination d'origine
        return resoudre_bande_complexe(self.re, self.im, np.asarray(br, dtype=np.float64),
                                       np.asarray(bi, dtype=np.float64), self.n, self.w)


def cinv(r: float, x: float) -> Tuple[float, float]:
    """Inverse d'un nombre complexe r + j*x -> (re, im)."""
    d = r * r + x * x
    return (r / d, -x / d)


def inv2(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float], d: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Inverse d'une matrice complexe 2x2 [[a, b], [c, d]]."""
    detr = a[0] * d[0] - a[1] * d[1] - (b[0] * c[0] - b[1] * c[1])
    deti = a[0] * d[1] + a[1] * d[0] - (b[0] * c[1] + b[1] * c[0])
    dd = detr * detr + deti * deti

    def q(x_c: Tuple[float, float]) -> Tuple[float, float]:
        return ((x_c[0] * detr + x_c[1] * deti) / dd, (x_c[1] * detr - x_c[0] * deti) / dd)

    return [q(d), q((-b[0], -b[1])), q((-c[0], -c[1])), q(a)]


def resoudre_ac(cfg: Dict[str, Any], charges: List[Dict[str, Any]], u_init: Optional[Dict[int, float]] = None) -> Dict[str, Any]:
    """Résolution nodale alternative (1x25 kV ou 2x25 kV)."""
    nv = int(cfg.get("nv", 2))
    normes = cfg.get("normes", {})
    deux = bool(cfg.get("deux", False))
    nc = 2 if deux else 1  # conducteurs par voie : 2 en 2x25 (caténaires + feeders), 1 en 1x25

    all_sst = cfg.get("sst", [])
    postes = cfg.get("postes", [])

    pts = [float(cfg["x_min"]), float(cfg["x_max"])]
    for s in all_sst:
        pts.append(float(s["x"]))
    for p in postes:
        pts.append(float(p["x"]))
    for c in charges:
        pts.append(float(c["x"]))

    xs = unique_positions(pts, tol=1e-3)
    m = len(xs)

    brk = np.zeros(m, dtype=np.uint8)  # coupure/section neutre à cet emplacement
    bus_of = np.full(m, -1, dtype=np.int32)
    sp_of = np.full(m, -1, dtype=np.int32)

    for j, s in enumerate(all_sst):
        k = pos_index(xs, float(s["x"]))
        brk[k] = 1
        bus_of[k] = j

    for j, p in enumerate(postes):
        k = pos_index(xs, float(p["x"]))
        if p.get("type") == "SP":
            brk[k] = 1
            sp_of[k] = j

    base = [0] * (m + 1)
    n = 0
    w = 0
    for i in range(m):
        base[i] = n
        n += (2 if brk[i] else 1) * nv * nc + (nc if bus_of[i] >= 0 and all_sst[bus_of[i]].get("actif") else 0)
    base[m] = n

    for i in range(m - 1):
        w = max(w, base[i + 2] - 1 - base[i])
    w = max(w, 2 * nv * nc + nc + 1)

    def node(idx_x: int, side: int, v_voie: int, c_cond: int) -> int:
        sd = side if brk[idx_x] else 0
        return base[idx_x] + (sd * nv + v_voie) * nc + c_cond

    def busn(idx_x: int, c_cond: int) -> int:
        return base[idx_x] + (2 if brk[idx_x] else 1) * nv * nc + c_cond

    # Admittance linéique
    if deux:
        zc = tuple(cfg["zc"])
        zf = tuple(cfg["zf"])
        zcf = tuple(cfg["zcf"])
        zi = inv2(zc, zcf, zcf, zf)

        def y_seg(dx_km: float):
            return [(z[0] / dx_km, z[1] / dx_km) for z in zi]
    else:
        zc = tuple(cfg["zc"])
        yc = cinv(zc[0], zc[1])

        def y_seg(dx_km: float):
            return [(yc[0] / dx_km, yc[1] / dx_km)]

    ixc = [pos_index(xs, float(c["x"])) for c in charges]
    un_nom = float(normes.get("un", 25000.0) or 25000.0)

    u_guess = []
    for c in charges:
        u0_c = u_init.get(c["id"]) if u_init and c["id"] in u_init else un_nom
        u_guess.append([float(u0_c or un_nom), 0.0])

    itr: List[Tuple[float, float]] = [(0.0, 0.0)] * len(charges)
    vr = np.zeros(n, dtype=np.float64)
    vi = np.zeros(n, dtype=np.float64)
    it_count = 0

    # Matrice nodale et sources des SST : indépendantes de l'itération (les trains
    # n'interviennent que dans le second membre) → construites une fois par pas de temps.
    A = BandC(n, w)
    br = np.zeros(n, dtype=np.float64)
    bi = np.zeros(n, dtype=np.float64)

    def y2(a_node: int, b_node: int, yr: float, yi: float):
        A.add(a_node, a_node, yr, yi)
        A.add(b_node, b_node, yr, yi)
        A.add(a_node, b_node, -yr, -yi)
        A.add(b_node, a_node, -yr, -yi)

    # Ligne de contact
    for i in range(m - 1):
        dx = max(xs[i + 1] - xs[i], 1e-4)
        Y = y_seg(dx)
        for v_idx in range(nv):
            if not deux:
                y2(node(i, 1, v_idx, 0), node(i + 1, 0, v_idx, 0), Y[0][0], Y[0][1])
            else:
                a0 = node(i, 1, v_idx, 0)
                a1 = node(i, 1, v_idx, 1)
                b0 = node(i + 1, 0, v_idx, 0)
                b1 = node(i + 1, 0, v_idx, 1)
                i2_nodes = [[a0, b0], [a1, b1]]
                for p_c in range(2):
                    for q_c in range(2):
                        yy = Y[p_c * 2 + q_c]
                        A.add(i2_nodes[p_c][0], i2_nodes[q_c][0], yy[0], yy[1])
                        A.add(i2_nodes[p_c][1], i2_nodes[q_c][1], yy[0], yy[1])
                        A.add(i2_nodes[p_c][0], i2_nodes[q_c][1], -yy[0], -yy[1])
                        A.add(i2_nodes[p_c][1], i2_nodes[q_c][0], -yy[0], -yy[1])

    # Admittance de fuite à la terre
    for i in range(n):
        A.add(i, i, 1e-9, 0.0)

    # Sous-stations
    for s in all_sst:
        if not s.get("actif"):
            if s.get("ponte"):
                kp0 = pos_index(xs, float(s["x"]))
                for v0 in range(nv):
                    for c0 in range(nc):
                        y2(node(kp0, 0, v0, c0), node(kp0, 1, v0, c0), 1000.0, 0.0)
            continue

        k_node = pos_index(xs, float(s["x"]))
        ys = cinv(float(s["zr"]), float(s["zx"]))
        e_volts = float(s.get("e", 27500.0) or 27500.0)

        for c_cond in range(nc):
            bn = busn(k_node, c_cond)
            e_source = (1.0 if c_cond == 0 else -1.0) * e_volts
            A.add(bn, bn, ys[0], ys[1])
            br[bn] += e_source * ys[0]
            bi[bn] += e_source * ys[1]
            for v_idx in range(nv):
                for sd in range(2):
                    y2(bn, node(k_node, sd, v_idx, c_cond), 1000.0, 0.0)

    # Postes
    for pp in postes:
        k_node = pos_index(xs, float(pp["x"]))
        if pp.get("type") == "SP" and pp.get("ferme"):
            for v_idx in range(nv):
                for c_cond in range(nc):
                    y2(node(k_node, 0, v_idx, c_cond), node(k_node, 1, v_idx, c_cond), 1000.0, 0.0)

        if pp.get("type") in ("SSP", "SP", "ATS"):
            # Mise en parallèle des voies
            num_sides = 2 if brk[k_node] else 1
            for sd in range(num_sides):
                for v2 in range(1, nv):
                    for c2 in range(nc):
                        y2(node(k_node, sd, 0, c2), node(k_node, sd, v2, c2), 1000.0, 0.0)

        if deux and pp.get("at") is not False:
            # Autotransformateurs : V_C + V_F ≈ 0
            zat = tuple(cfg["zat"])
            ya = cinv(zat[0], zat[1])
            num_sides = 2 if brk[k_node] else 1
            for sd in range(num_sides):
                for v3 in range(nv):
                    c_node = node(k_node, sd, v3, 0)
                    f_node = node(k_node, sd, v3, 1)
                    A.add(c_node, c_node, ya[0], ya[1])
                    A.add(f_node, f_node, ya[0], ya[1])
                    A.add(c_node, f_node, ya[0], ya[1])
                    A.add(f_node, c_node, ya[0], ya[1])

    A_base, br_base, bi_base = A, br, bi

    for it_count in range(30):
        A = A_base.copie()  # solve() factorise A sur place
        br = br_base.copy()
        bi = bi_base.copy()

        # Charges (trains)
        for c3, ch in enumerate(charges):
            um = math.hypot(u_guess[c3][0], u_guess[c3][1])
            pk = limite_p(float(ch["p_kw"]), max(um, 100.0), normes, float(ch.get("kp", 1.0))) * 1000.0
            cos_phi = min(max(float(ch.get("cos_phi", 0.98) or 0.98), 0.1), 1.0)
            tg = math.tan(math.acos(cos_phi)) * (1.0 if pk >= 0 else 0.0)
            sr = pk
            si = pk * tg
            ur = u_guess[c3][0]
            ui = u_guess[c3][1]
            u2 = max(ur * ur + ui * ui, 1e4)

            # I = conj(S / V) = ((Sr + j Si) / (ur + j ui))* = (Sr*ur + Si*ui)/u2 + j (Sr*ui - Si*ur)/u2
            ir = (sr * ur + si * ui) / u2
            ii = (sr * ui - si * ur) / u2
            itr[c3] = (ir, ii)

            v_voie = min(max(int(ch.get("voie", 1)), 1), nv) - 1
            nd = node(ixc[c3], 0, v_voie, 0)
            br[nd] -= ir
            bi[nd] -= ii

        vr, vi = A.solve(br, bi)

        # Convergence
        err = 0.0
        for c3, ch in enumerate(charges):
            v_voie = min(max(int(ch.get("voie", 1)), 1), nv) - 1
            nd2 = node(ixc[c3], 0, v_voie, 0)
            nr = vr[nd2]
            ni = vi[nd2]
            err = max(err, math.hypot(nr - u_guess[c3][0], ni - u_guess[c3][1]))
            if it_count > 8:
                u_guess[c3] = [0.5 * (u_guess[c3][0] + nr), 0.5 * (u_guess[c3][1] + ni)]
            else:
                u_guess[c3] = [nr, ni]

        if err < 5.0:
            break

    # Résultats
    res: Dict[str, Any] = {
        "u": {},
        "i": {},
        "p": {},
        "vrail": {},
        "sst_i": [],
        "sst_p": [],
        "sst_s": [],
        "sst_q": [],
        "sst_u": [],
        "fd_g": [],
        "fd_d": [],
        "pertes_ligne": 0.0,
        "pertes_sst": 0.0,
        "rheostat": 0.0,
        "iter": it_count + 1,
    }

    stot = 0.0
    for s in all_sst:
        k_node = pos_index(xs, float(s["x"]))
        P = 0.0
        Q = 0.0
        imax = 0.0
        umin = float("inf")
        fg = 0.0
        fd = 0.0

        if s.get("actif"):
            ys = cinv(float(s["zr"]), float(s["zx"]))
            e_volts = float(s.get("e", 27500.0) or 27500.0)
            for c_cond in range(nc):
                bn = busn(k_node, c_cond)
                e_source = (1.0 if c_cond == 0 else -1.0) * e_volts
                dr = e_source - vr[bn]
                di = -vi[bn]
                ir_sst = dr * ys[0] - di * ys[1]
                ii_sst = dr * ys[1] + di * ys[0]
                P += e_source * ir_sst
                Q += -e_source * ii_sst
                imax = max(imax, math.hypot(ir_sst, ii_sst))
                umin = min(umin, math.hypot(vr[bn], vi[bn]))
                res["pertes_sst"] += (ir_sst * ir_sst + ii_sst * ii_sst) * float(s["zr"]) / 1000.0

                if c_cond == 0:
                    for v_idx in range(nv):
                        nl = node(k_node, 0, v_idx, 0)
                        nr = node(k_node, 1, v_idx, 0)
                        fg += math.hypot(vr[bn] - vr[nl], vi[bn] - vi[nl]) * 1000.0
                        fd += math.hypot(vr[bn] - vr[nr], vi[bn] - vi[nr]) * 1000.0

        res["sst_p"].append(P / 1000.0)
        res["sst_q"].append(Q / 1000.0)
        res["sst_s"].append(math.hypot(P, Q) / 1000.0)
        res["sst_i"].append(imax)
        res["sst_u"].append(umin if math.isfinite(umin) else float(s.get("e", 27500.0)))
        res["fd_g"].append(fg)
        res["fd_d"].append(fd)
        stot += P / 1000.0

    emax = max([float(s.get("e", 27500.0)) for s in all_sst if s.get("actif")] or [0.0])
    pc = 0.0

    for q, ch in enumerate(charges):
        v_voie = min(max(int(ch.get("voie", 1)), 1), nv) - 1
        nd = node(ixc[q], 0, v_voie, 0)
        ur_t = vr[nd]
        ui_t = vi[nd]
        i_curr = itr[q]

        # Tronçon non alimenté
        if not emax or math.hypot(ur_t, ui_t) > 1.25 * emax:
            ur_t = 0.0
            ui_t = 0.0
            i_curr = (0.0, 0.0)

        c_id = ch["id"]
        res["u"][c_id] = math.hypot(ur_t, ui_t)
        res["i"][c_id] = math.hypot(i_curr[0], i_curr[1]) * (-1.0 if float(ch["p_kw"]) < 0 else 1.0)
        p_ch = (ur_t * i_curr[0] + ui_t * i_curr[1]) / 1000.0
        res["p"][c_id] = p_ch
        res["vrail"][c_id] = 0.0
        pc += p_ch

    res["pertes_ligne"] = max(0.0, stot - res["pertes_sst"] - pc)
    return res
