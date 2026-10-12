"""
Module de dimensionnement et d'implantation automatique des sous-stations de traction.
- Recherche du nombre minimal de sous-stations par renforcement successif du point faible
- Vérification combinatoire en situation normale et dégradée N-1
- Sélection des calibres normalisés de puissance (transformateurs / groupes redresseurs)
- Comparaison de puissances unitaires imposées (ex: 3 MW vs 6 MW ou 20 MVA vs 40 MVA).
"""

import time
import math
from typing import List, Dict, Any, Optional, Callable
import numpy as np

from .simulation import SimulationEnv, build_network_configuration, build_configuration_n1, calculer_profils_isoles, simuler, analyser


def dimensionner(
    env: SimulationEnv,
    dim_opts: Optional[Dict[str, Any]] = None,
    prog_callback: Optional[Callable[[float], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """Exécute l'algorithme d'optimisation d'implantation et de puissance des sous-stations."""
    t0 = time.time()
    D = dim_opts or {}
    ac = (env.famille != "cc3000")
    alim0 = env.P.get("alimentation") or {}
    dt = float(D.get("dt", 5.0) or 5.0)

    def log(msg: str):
        if log_callback:
            log_callback(msg)

    def progress(f: float):
        if prog_callback:
            prog_callback(f)

    profils = calculer_profils_isoles(env, dt)
    d0 = float(env.troncons[0]["pk_ini"])
    d1 = float(env.troncons[-1]["pk_fin"])
    L = d1 - d0

    cands_raw = D.get("candidats") or []
    cands = sorted(
        [
            {
                "nom": c.get("nom") or f"Site PK {float(c.get('pk', 0)):.1f}",
                "pk": float(c["pk"]),
                "scc_mva": float(c.get("scc_mva", 2000.0) or 2000.0),
            }
            for c in cands_raw
            if c.get("pk") is not None and str(c.get("pk")).strip() != ""
        ],
        key=lambda x: x["pk"]
    )

    pas_max = float(D.get("pas_max_km", 60.0 if ac else 25.0) or (60.0 if ac else 25.0))
    pas_min = float(D.get("pas_min_km", 25.0 if ac else 8.0) or (25.0 if ac else 8.0))

    puissances_raw = D.get("puissances", "")
    if isinstance(puissances_raw, list):
        std_p = [float(x) for x in puissances_raw if float(x) > 0]
    else:
        std_p = [float(x.replace(",", ".").strip()) for x in str(puissances_raw).replace(";", " ").replace("/", " ").split() if x.strip() and float(x.replace(",", ".").strip()) > 0]
    std_p.sort()

    sN = float(D.get("surcharge_n", 1.0) or 1.0)
    sN1 = float(D.get("surcharge_n1", 1.5) or 1.5)
    sP = float(D.get("surcharge_pointe", 2.0 if ac else 3.0) or (2.0 if ac else 3.0))

    pU_val = D.get("p_unite")
    pU = float(str(pU_val).replace(",", ".").strip()) if pU_val not in (None, "") else 0.0
    if pU > 0:
        std_p = [pU]

    tmpl_sst = (alim0.get("sst") or [{}])[0] if (alim0.get("sst")) else {}
    u0cc = float(tmpl_sst.get("u0", 3600.0) or 3600.0)
    chute_pct = float(str(D.get("chute_pct", 6.0) or 6.0).replace(",", "."))

    def r_int_pour(p_kw: float) -> float:
        inom = p_kw * 1000.0 / float(env.normes.get("un", 3000.0))
        return round(chute_pct / 100.0 * u0cc / max(inom, 1.0), 4)

    def make_sst_at(pk: float, nom: str, scc: float = 2000.0) -> Dict[str, Any]:
        if ac:
            s_nom_val = (std_p[-1] / 1000.0) if std_p else 40.0
            return {
                "nom": nom,
                "pk": round(pk, 3),
                "s_nom_mva": s_nom_val,
                "ucc_pct": float(tmpl_sst.get("ucc_pct", 10.0) or 10.0),
                "scc_mva": scc or float(tmpl_sst.get("scc_mva", 2000.0) or 2000.0),
                "u0": float((alim0.get("ac") or {}).get("u0", 27500.0) or 27500.0),
                "en_service": "oui",
            }
        return {
            "nom": nom,
            "pk": round(pk, 3),
            "u0": u0cc,
            "r_int": r_int_pour(pU) if pU > 0 else float(tmpl_sst.get("r_int", 0.05) or 0.05),
            "p_nom_kw": std_p[-1] if std_p else 9000.0,
            "en_service": "oui",
        }

    def make_postes_pour(pks: List[float]) -> List[Dict[str, Any]]:
        out = []
        s_sorted = sorted(pks)
        if ac:
            pas_at = float(D.get("pas_at_km", 15.0 if env.systeme == "ac2x25" else 20.0) or 15.0)
            for i in range(len(s_sorted) - 1):
                mid_pk = (s_sorted[i] + s_sorted[i + 1]) / 2.0
                out.append({"nom": f"SP PK {mid_pk:.1f}", "pk": round(mid_pk, 3), "type": "SP"})

            marks = [d0]
            for i, x in enumerate(s_sorted):
                marks.append(x)
                if i < len(s_sorted) - 1:
                    marks.append((x + s_sorted[i + 1]) / 2.0)
            marks.append(d1)

            for j in range(len(marks) - 1):
                a_m = marks[j]
                b_m = marks[j + 1]
                k_div = int(math.ceil((b_m - a_m) / pas_at))
                for q in range(1, k_div):
                    x_at = a_m + (b_m - a_m) * q / k_div
                    p_type = "ATS" if env.systeme == "ac2x25" else "SSP"
                    out.append({"nom": f"{p_type} PK {x_at:.1f}", "pk": round(x_at, 3), "type": p_type})
        else:
            pas_ps = float(D.get("pas_ps_km", 10.0) or 10.0)
            for i in range(len(s_sorted) - 1):
                if s_sorted[i + 1] - s_sorted[i] > pas_ps:
                    xm = (s_sorted[i] + s_sorted[i + 1]) / 2.0
                    out.append({"nom": f"PS PK {xm:.1f}", "pk": round(xm, 3), "type": "PS"})

        out.sort(key=lambda p: p["pk"])
        return out

    def evaluer(sst_l: List[Dict[str, Any]], postes_l: List[Dict[str, Any]], avec_n1: bool) -> Dict[str, Any]:
        cas = [{"nom": "normale", "k": None, "ov": {"sst": sst_l, "postes": postes_l}}]
        if avec_n1:
            for k, s in enumerate(sst_l):
                if n1_interm and len(sst_l) > 2 and (k == 0 or k == len(sst_l) - 1):
                    continue
                cas.append({"nom": f"N-1 {s['nom']}", "k": k, "ov": {"sst": sst_l, "postes": postes_l}})

        out_eval: Dict[str, Any] = {
            "cas": [],
            "ok": True,
            "marge": float("inf"),
            "pire": None,
            "marge_cap": float("inf"),
            "pire_cap": None,
        }

        for c_item in cas:
            cfg_ev = build_network_configuration(env, c_item["ov"]) if c_item["k"] is None else build_configuration_n1(env, c_item["k"], c_item["ov"])
            R_ev = simuler(env, {"cfg": cfg_ev, "profils": profils, "dt": dt})
            A_ev = analyser(env, R_ev)

            deg = (c_item["k"] is not None)
            N_norm = env.normes
            su = float(N_norm.get("umin2") if deg else N_norm.get("umin1"))
            sz = float(N_norm.get("umoy_zone_degrade") if deg else N_norm.get("umoy_zone"))
            un_val = float(N_norm.get("un", 3000.0))

            m1 = (A_ev["glob"]["u_min"] - su) / un_val
            m2 = (A_ev["glob"]["u_moy_zone_min"] - sz) / un_val if math.isfinite(A_ev["glob"]["u_moy_zone_min"]) else 1.0
            marge_cas = min(m1, m2)

            cap_eval = None
            if pU > 0:
                pire_c = None
                for k_sst, sst_st in enumerate(A_ev["sst"]):
                    if not sst_st.get("actif"):
                        continue
                    pt = sst_st["s_1min"] if ac else sst_st["p_1min"]
                    ch = sst_st["charge"]
                    taux = max(ch / ((sN1 if deg else sN) * pU), pt / (sP * pU))
                    if pire_c is None or taux > pire_c["taux"]:
                        pire_c = {"k": k_sst, "taux": taux, "nom": sst_st["nom"]}
                if pire_c:
                    cap_eval = {"marge": 1.0 - pire_c["taux"], "taux": pire_c["taux"], "nom": pire_c["nom"], "k": pire_c["k"]}

            out_eval["cas"].append({
                "nom": c_item["nom"],
                "k": c_item["k"],
                "A": A_ev,
                "marge": marge_cas,
                "marge_cap": cap_eval["marge"] if cap_eval else None,
            })

            if marge_cas < out_eval["marge"]:
                out_eval["marge"] = marge_cas
                out_eval["pire"] = {
                    "cas": c_item["nom"],
                    "k": c_item["k"],
                    "pk": A_ev["glob"]["pire"]["pk_u_min"] if A_ev["glob"]["pire"] else None,
                }

            if cap_eval and cap_eval["marge"] < out_eval["marge_cap"]:
                out_eval["marge_cap"] = cap_eval["marge"]
                out_eval["pire_cap"] = {
                    "cas": c_item["nom"],
                    "pk": float(sst_l[cap_eval["k"]]["pk"]),
                    "nom": cap_eval["nom"],
                    "taux": cap_eval["taux"],
                }

        out_eval["ok_u"] = (out_eval["marge"] >= 0.0)
        out_eval["ok_cap"] = not (out_eval["marge_cap"] < 0.0)
        out_eval["ok"] = bool(out_eval["ok_u"] and out_eval["ok_cap"])

        if out_eval["ok_u"] and not out_eval["ok_cap"] and out_eval["pire_cap"]:
            out_eval["pire"] = {
                "cas": out_eval["pire_cap"]["cas"],
                "pk": out_eval["pire_cap"]["pk"],
                "cap": True,
                "nom": out_eval["pire_cap"]["nom"],
            }

        return out_eval

    def placer(n_sst: int) -> List[Any]:
        pks = []
        if n_sst == 1:
            pks.append(d0 + L / 2.0)
        else:
            a_ext = min(L / (n_sst - 1 + 0.5) * 0.25, L / 4.0)
            sp = (L - 2.0 * a_ext) / (n_sst - 1)
            for i in range(n_sst):
                pks.append(d0 + a_ext + sp * i)

        if not cands:
            return [round(x * 2.0) / 2.0 for x in pks]

        used = set()
        out_cands = []
        for x in pks:
            best_idx = -1
            best_d = float("inf")
            for j, c in enumerate(cands):
                if j not in used and abs(c["pk"] - x) < best_d:
                    best_d = abs(c["pk"] - x)
                    best_idx = j
            if best_idx >= 0:
                used.add(best_idx)
                out_cands.append(best_idx)
        out_cands.sort()
        return out_cands

    def liste_sst(positions: List[Any]) -> List[Dict[str, Any]]:
        out = []
        for i, pos_item in enumerate(positions):
            if cands:
                c = cands[pos_item]
                out.append(make_sst_at(c["pk"], c["nom"], c["scc_mva"]))
            else:
                pk_val = float(pos_item)
                out.append(make_sst_at(pk_val, f"SST {i + 1} (PK {pk_val:.1f})"))
        return out

    n_min = max(1, int(math.ceil(L / pas_max)))
    n_max = max(n_min, int(math.ceil(L / pas_min)) + 2)
    if cands:
        n_max = min(n_max, len(cands))

    avec_n1 = (D.get("n1") not in (False, "non"))
    n1_interm = (D.get("n1") == "interm")

    def cle(pos_list: List[Any]) -> str:
        return ",".join(str(x) for x in sorted(pos_list))

    def eval_pos(pos_list: List[Any], n1_flag: bool):
        sl = liste_sst(pos_list)
        pst = make_postes_pour([float(s["pk"]) for s in sl])
        return {"pos": list(pos_list), "sl": sl, "pst": pst, "ev": evaluer(sl, pst, n1_flag)}

    def inserer(pos_list: List[Any], xw: float, k_out: Optional[int]) -> Optional[List[Any]]:
        if cands:
            best_idx = -1
            best_d = float("inf")
            for j, c in enumerate(cands):
                if j not in pos_list and abs(c["pk"] - xw) < best_d:
                    best_d = abs(c["pk"] - xw)
                    best_idx = j
            if best_idx < 0:
                return None
            new_p = list(pos_list) + [best_idx]
            new_p.sort()
            return new_p

        x_val = round(min(max(xw, d0), d1) * 2.0) / 2.0
        trop = lambda y: any(abs(float(p) - y) < pas_min - 1e-6 for p in pos_list)

        if trop(x_val):
            # Déplacement progressif ou insertion au milieu
            all_pts = sorted([float(p) for p in pos_list] + [d0, d1])
            essais_x = []
            for q in range(len(all_pts) - 1):
                mid = round((all_pts[q] + all_pts[q + 1]) / 2.0 * 2.0) / 2.0
                dist_weak = 0.0 if (all_pts[q] <= xw <= all_pts[q + 1]) else min(abs(xw - all_pts[q]), abs(xw - all_pts[q + 1]))
                essais_x.append({"x": mid, "d": dist_weak})
            essais_x.sort(key=lambda item: item["d"])

            x_cand = None
            for e_item in essais_x:
                if not trop(e_item["x"]) and e_item["d"] <= pas_max:
                    x_cand = e_item["x"]
                    break
            if x_cand is None:
                return None
            x_val = x_cand

        new_p = list(pos_list) + [x_val]
        new_p.sort()
        return new_p

    pos = placer(n_min)
    etat = None
    vus = {}
    dernier_echec = ""
    ins_cap = 0
    essais = []

    for tour in range(150):
        progress(min(0.9, tour / 40.0))
        r_eval = eval_pos(pos, False)
        marge_pct = r_eval["ev"]["marge"] * 100.0
        log(f"{len(pos)} SST : situation normale, marge de tension {marge_pct:.1f} %")
        essais.append({"n": len(pos), "pks": [float(s["pk"]) for s in r_eval["sl"]], "marge": r_eval["ev"]["marge"], "pire": r_eval["ev"]["pire"]})

        if r_eval["ev"]["ok"] and avec_n1:
            r1 = eval_pos(pos, True)
            essais[-1]["marge_n1"] = r1["ev"]["marge"]
            log(f"{len(pos)} SST : critère N-1, marge de tension {r1['ev']['marge'] * 100:.1f} % ({r1['ev']['pire']['cas'] if r1['ev']['pire'] else 'ok'})")
            if r1["ev"]["ok"]:
                etat = r1
                break
            r_eval = r1
        elif r_eval["ev"]["ok"]:
            etat = r_eval
            break

        if len(pos) >= n_max:
            break

        pire_pk = r_eval["ev"]["pire"]["pk"] if (r_eval["ev"]["pire"] and r_eval["ev"]["pire"].get("pk") is not None) else (d0 + d1) / 2.0
        np_pos = inserer(pos, pire_pk, r_eval["ev"]["pire"].get("k") if r_eval["ev"]["pire"] else None)
        if not np_pos or cle(np_pos) in vus:
            break
        vus[cle(np_pos)] = 1
        pos = np_pos

    retenu = etat
    if retenu:
        # Élagage des sous-stations redondantes
        change = True
        while change and len(retenu["pos"]) > 1:
            change = False
            ordre_idx = list(range(len(retenu["pos"])))
            ordre_idx.sort(key=lambda idx: retenu["ev"]["cas"][0]["A"]["sst"][idx]["charge"])
            for idx_cand in ordre_idx:
                cand_pos = [p for k, p in enumerate(retenu["pos"]) if k != idx_cand]
                rr = eval_pos(cand_pos, False)
                if not rr["ev"]["ok"]:
                    continue
                if avec_n1:
                    rr = eval_pos(cand_pos, True)
                    if not rr["ev"]["ok"]:
                        continue
                log(f"Élagage : {retenu['sl'][idx_cand]['nom']} n'est pas nécessaire")
                retenu = rr
                change = True
                break

    if not retenu:
        return {
            "ok": False,
            "essais": essais,
            "duree": time.time() - t0,
            "p_unite": pU or None,
            "message": f"Aucune solution trouvée (jusqu'à {n_max} sous-stations, pas minimal {pas_min} km).",
        }

    # Calcul des besoins en puissance par sous-station
    besoins = []
    for k, s in enumerate(retenu["sl"]):
        nrm = retenu["ev"]["cas"][0]["A"]["sst"][k]
        cN = nrm["charge"]
        cP = nrm["s_1min"] if ac else nrm["p_1min"]
        cN1 = 0.0
        cas_n1 = ""
        for c_cas in retenu["ev"]["cas"][1:]:
            x_sst = c_cas["A"]["sst"][k]
            if not x_sst.get("actif"):
                continue
            v_ch = x_sst["charge"]
            if v_ch > cN1:
                cN1 = v_ch
                cas_n1 = c_cas["nom"]
            cP = max(cP, x_sst["s_1min"] if ac else x_sst["p_1min"])

        req = max(cN / sN, cN1 / sN1, cP / sP)
        if pU > 0:
            choix = pU
        else:
            candidates = [p for p in std_p if p >= req]
            choix = candidates[0] if candidates else (int(math.ceil(req / 500.0)) * 500 if not std_p else None)

        besoins.append({
            "nom": s["nom"],
            "pk": float(s["pk"]),
            "charge_n": cN,
            "charge_n1": cN1,
            "cas_n1": cas_n1,
            "pointe": cP,
            "requis": req,
            "choix": choix,
            "taux": (req / choix) if choix else None,
            "desequilibre_pct": nrm.get("desequilibre_pct"),
            "scc": s.get("scc_mva", 2000.0),
        })

    for k, s in enumerate(retenu["sl"]):
        if ac:
            s["s_nom_mva"] = (besoins[k]["choix"] / 1000.0) if besoins[k]["choix"] else s.get("s_nom_mva", 20.0)
        else:
            s["p_nom_kw"] = besoins[k]["choix"] or s.get("p_nom_kw", 6000.0)

    progress(1.0)
    gN = retenu["ev"]["cas"][0]["A"]["glob"]

    cas_summary = [
        {
            "nom": c["nom"],
            "marge": c["marge"],
            "u_min": c["A"]["glob"]["u_min"],
            "u_moy": c["A"]["glob"]["u_moy_zone_min"],
        }
        for c in retenu["ev"]["cas"]
    ]

    return {
        "ok": True,
        "n": len(retenu["sl"]),
        "sst": retenu["sl"],
        "postes": retenu["pst"],
        "besoins": besoins,
        "cas": cas_summary,
        "essais": essais,
        "duree": time.time() - t0,
        "dt": dt,
        "p_unite": pU or None,
        "l_km": L,
        "d0": d0,
        "d1": d1,
        "pertes_kwh": gN["pertes_ligne_kwh"] + gN["pertes_sst_kwh"],
        "energie_kwh": gN["energie_sst_kwh"],
        "taux_max": max((b["requis"] / b["choix"] for b in besoins if b["choix"]), default=0.0),
    }


def comparer_variantes(
    env: SimulationEnv,
    variantes: List[float],
    dim_opts: Optional[Dict[str, Any]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> List[Dict[str, Any]]:
    """Compare une liste de puissances unitaires normalisées (ex: 3 MW et 6 MW)."""
    out = []
    base_d = dict(dim_opts or {})
    for pu in variantes:
        d_var = dict(base_d)
        d_var["p_unite"] = pu
        unit_str = "kVA" if env.famille != "cc3000" else "kW"
        if log_callback:
            log_callback(f"=== Recherche pour sous-stations de {pu:.0f} {unit_str} ===")
        res = dimensionner(env, d_var, log_callback=log_callback)
        res["p_unite"] = pu
        out.append(res)
    return out
