"""
Noyaux de calcul compilés (Numba) pour les boucles critiques du moteur.

Chaque noyau reproduit exactement les opérations de la version Python d'origine, dans le même
ordre : les résultats sont identiques au bit près (vérifié par tests/validation_v1).
Sans Numba, les mêmes fonctions s'exécutent en Python pur (plus lentement).
"""

import math

import numpy as np

try:
    from numba import njit
    NUMBA = True
except ImportError:  # pragma: no cover - repli sans compilation
    NUMBA = False

    def njit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda f: f


@njit(cache=True)
def resoudre_bande_reelle(a, b, n, w):
    """
    Élimination de Gauss sans pivotage sur une matrice bande réelle stockée en (n, 2w+1).
    `a` est modifiée sur place (facteurs LU) ; retourne la solution.
    """
    b_res = b.copy()
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


@njit(cache=True)
def resoudre_bande_complexe(R, I_mat, br, bi, n, w):
    """
    Élimination de Gauss sans pivotage sur une matrice bande complexe (parties réelle R et
    imaginaire I_mat stockées en (n, 2w+1)). R et I_mat sont modifiées sur place.
    """
    b_r = br.copy()
    b_i = bi.copy()
    for k in range(n):
        pr = R[k, w]
        pi = I_mat[k, w]
        pd = pr * pr + pi * pi
        if pd < 1e-28:
            pr = 1e-14
            R[k, w] = pr
            pd = 1e-28

        iend = min(n - 1, k + w)
        for i in range(k + 1, iend + 1):
            ik = k - i + w
            ar = R[i, ik]
            ai = I_mat[i, ik]
            if ar == 0.0 and ai == 0.0:
                continue
            fr = (ar * pr + ai * pi) / pd
            fi = (ai * pr - ar * pi) / pd
            R[i, ik] = fr
            I_mat[i, ik] = fi

            for j in range(k + 1, iend + 1):
                kj = j - k + w
                ij = j - i + w
                cr = R[k, kj]
                ci = I_mat[k, kj]
                R[i, ij] -= fr * cr - fi * ci
                I_mat[i, ij] -= fr * ci + fi * cr

            b0r = b_r[k]
            b0i = b_i[k]
            b_r[i] -= fr * b0r - fi * b0i
            b_i[i] -= fr * b0i + fi * b0r

    for k in range(n - 1, -1, -1):
        sr = b_r[k]
        si = b_i[k]
        jend = min(n - 1, k + w)
        for j in range(k + 1, jend + 1):
            kj2 = j - k + w
            xr = b_r[j]
            xi = b_i[j]
            sr -= R[k, kj2] * xr - I_mat[k, kj2] * xi
            si -= R[k, kj2] * xi + I_mat[k, kj2] * xr

        dr = R[k, w]
        di = I_mat[k, w]
        dd = dr * dr + di * di
        b_r[k] = (sr * dr + si * di) / dd
        b_i[k] = (si * dr - sr * di) / dd
    return b_r, b_i


@njit(cache=True)
def _bcap(v_ms, decel_service, f_frein, p_frein_kw, davis_a, davis_b, davis_c, masse_dyn_t):
    """Copie de Marche.bcap / Train.effort_frein_elec / Train.resistance (tunnel nul)."""
    v_kmh = v_ms * 3.6
    vf = max(v_kmh, 1.0)
    if vf <= 0.1 or f_frein <= 0:
        f_el = 0.0
    elif p_frein_kw > 0:
        f_el = min(f_frein, p_frein_kw * 3.6 / vf)
    else:
        f_el = f_frein
    r = davis_a + davis_b * v_kmh + davis_c * v_kmh * v_kmh
    r = r * (1.0 + 0.0)
    frein = (f_el + r) / masse_dyn_t
    return max(max(decel_service, frein), 0.05)


@njit(cache=True)
def enveloppe_retrograde(e, ds, decel_service, f_frein, p_frein_kw, davis_a, davis_b, davis_c, masse_dyn_t):
    """Intégration rétrograde de l'enveloppe de vitesse (m/s), sur place : e[i] ≤ √(e[i+1]² + 2·b·ds)."""
    n = e.shape[0]
    for i in range(n - 2, -1, -1):
        v_next = e[i + 1]
        b = _bcap(v_next, decel_service, f_frein, p_frein_kw, davis_a, davis_b, davis_c, masse_dyn_t)
        lim = math.sqrt(v_next * v_next + 2.0 * b * ds)
        if e[i] > lim:
            e[i] = lim
    return e


def prechauffer():
    """Compile les noyaux à l'avance (évite la latence au premier calcul)."""
    a = np.ones((2, 3))
    resoudre_bande_reelle(a, np.ones(2), 2, 1)
    resoudre_bande_complexe(np.ones((2, 3)), np.zeros((2, 3)), np.ones(2), np.zeros(2), 2, 1)
    enveloppe_retrograde(np.ones(3), 2.0, 0.2, 100.0, 2000.0, 2.0, 0.02, 0.0004, 100.0)
    minimum_glissant(np.ones(3), 1)


@njit(cache=True)
def minimum_glissant(vl, k):
    """out[i] = min(vl[i-k .. i]) par file monotone (même algorithme que la version à deque)."""
    n = vl.shape[0]
    out = np.zeros(n, dtype=np.float64)
    dq = np.empty(n, dtype=np.int64)
    tete = 0
    queue = 0  # dq[tete:queue] = indices candidats, valeurs croissantes
    for i in range(n):
        while queue > tete and vl[dq[queue - 1]] >= vl[i]:
            queue -= 1
        dq[queue] = i
        queue += 1
        if dq[tete] < i - k:
            tete += 1
        out[i] = vl[dq[tete]]
    return out
