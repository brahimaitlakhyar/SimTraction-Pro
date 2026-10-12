"""
Orchestrateur de simulation multi-trains et calcul des grandeurs normatives (EN 50163, EN 50388-1).
- Intégration temporelle pas à pas multi-trains
- Couplage tension-marche (effort réel fonction de la tension instantanée)
- Analyse des situations normales et dégradées N-1
- Bilan énergétique, puissances 1 min / 15 min / 1 h et conformité réglementaire.
"""

import time
import math
from typing import List, Dict, Any, Optional, Tuple, Callable
import numpy as np

from .train import Train
from .track import Coord, extract_gares
from .kinematics import Marche
from .solver_dc import resoudre_cc, limite_p
from .solver_ac import resoudre_ac
from .standards import merge_standards, get_system_family


def parse_time_s(val: Any) -> float:
    """Parse une heure au format hh:mm:ss, hh:mm ou en secondes numériques."""
    if isinstance(val, (int, float)):
        return float(val)
    parts = [float(p.replace(",", ".").strip() or 0.0) for p in str(val or "0").split(":") if p.strip()]
    while len(parts) < 3:
        parts.append(0.0)
    return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]


def format_hms(t_sec: float) -> str:
    """Formate des secondes en hh:mm:ss."""
    t = int(round(t_sec))
    h = t // 3600
    m = (t % 3600) // 60
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_arrets_dict(txt: str) -> Dict[str, float]:
    """Parse la chaîne d'arrêts 'Gare A:60 ; Gare B:120' en dictionnaire {nom: duree_s}."""
    out: Dict[str, float] = {}
    for part in str(txt or "").replace("\n", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        idx = part.rfind(":")
        if idx > 0:
            nom = part[:idx].strip()
            try:
                duree = float(part[idx + 1:].replace(",", ".").strip())
                if nom:
                    out[nom] = duree
            except ValueError:
                pass
    return out


def moy_max(arr: np.ndarray, offset: int, stride: int, n: int, w: int) -> float:
    """Valeur maximale d'une moyenne glissante sur une fenêtre w échantillons."""
    if n <= 0:
        return 0.0
    w = max(1, min(w, n))
    s = 0.0
    best = -float("inf")
    for i in range(n):
        s += float(arr[offset + i * stride])
        if i >= w:
            s -= float(arr[offset + (i - w) * stride])
        if i >= w - 1:
            val = s / w
            if val > best:
                best = val
    return best if math.isfinite(best) else 0.0


class SimulationEnv:
    def __init__(self, project_data: Dict[str, Any]):
        self.P = project_data
        self.systeme = project_data.get("systeme", "cc3000")
        self.famille = get_system_family(self.systeme)
        self.normes = merge_standards(self.systeme, project_data.get("normes"))

        # Tracé
        trs_raw = (project_data.get("trace") or {}).get("troncons") or []
        self.troncons = sorted(
            [t for t in trs_raw if float(t.get("pk_fin", 0)) > float(t.get("pk_ini", 0))],
            key=lambda x: float(x["pk_ini"])
        )
        if not self.troncons:
            raise ValueError("Le tracé est vide : saisir au moins un tronçon valide.")

        self.coord = Coord(self.troncons)
        self.gares = extract_gares(self.troncons)
        gares_set = {g["nom"] for g in self.gares}

        # Matériel roulant
        self.trains: Dict[Any, Train] = {}
        for t_dict in project_data.get("trains") or []:
            tr = Train(t_dict)
            self.trains[tr.ref] = tr

        # Circulations
        self.circ: List[Dict[str, Any]] = []
        self.avert: List[str] = []
        duree_s = float(project_data.get("duree_s", 3600.0) or 3600.0)
        periode_s = float(project_data.get("periode_s", 0.0) or 0.0)

        for n_line, r in enumerate(project_data.get("trafic") or []):
            ref = r.get("ref_train")
            if ref not in self.trains:
                if ref is not None:
                    self.avert.append(f"Trafic ligne {n_line + 1} : engin réf {ref} absent du matériel.")
                continue

            sens = -1 if int(r.get("sens", 1)) == 2 else 1
            arr = parse_arrets_dict(r.get("arrets", ""))
            for g in list(arr.keys()):
                if g not in gares_set:
                    self.avert.append(f"Trafic ligne {n_line + 1} : gare « {g} » absente du tracé.")
                    del arr[g]

            self.circ.append({
                "ref_train": ref,
                "sens": sens,
                "depart_s": parse_time_s(r.get("depart", 0.0)),
                "voie": int(r.get("voie", 1 if sens > 0 else 2)),
                "v_initiale": float(r.get("v_initiale", 0.0) or 0.0),
                "arrets": arr,
                "libelle": r.get("libelle", ""),
            })

        # Cadencement / répétition de la grille
        if periode_s > 0:
            base_circ = list(self.circ)
            for k in range(1, 200):
                add_circ = [c for c in base_circ if c["depart_s"] + k * periode_s < duree_s]
                if not add_circ:
                    break
                for c in add_circ:
                    c_rep = dict(c)
                    c_rep["depart_s"] = c["depart_s"] + k * periode_s
                    c_rep["arrets"] = dict(c["arrets"])
                    self.circ.append(c_rep)

        self.circ = [c for c in self.circ if c["depart_s"] < duree_s]
        self.circ.sort(key=lambda x: x["depart_s"])

        for i, c in enumerate(self.circ):
            c["id"] = i
            t0 = int(round(c["depart_s"]))
            tr_nom = self.trains[c["ref_train"]].nom.split("(")[0].strip()
            c["nom"] = c.get("libelle") or f"{tr_nom} {t0 // 3600:02d}:{(t0 % 3600) // 60:02d}"

        self.duree = duree_s
        self.marge = float(project_data.get("marge_croisiere", 0.98) or 0.98)
        self.vligne = float((project_data.get("trace") or {}).get("vitesse_ligne", 0.0) or 0.0)


def build_network_configuration(env: SimulationEnv, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Construit la configuration topologique et électrique du réseau."""
    ov = override or {}
    P = env.P
    alim = P.get("alimentation") or {}
    sst_list = ov.get("sst") or alim.get("sst") or []
    postes_list = ov.get("postes") or alim.get("postes") or []
    hs = ov.get("hors_service") or {}

    nv = int((alim.get("cc") if env.famille == "cc3000" else alim.get("ac") or {}).get("nb_voies", 2))
    cfg: Dict[str, Any] = {
        "famille": env.famille,
        "normes": env.normes,
        "nv": nv,
        "x_min": 0.0,
        "x_max": env.coord.total,
        "sst_src": sst_list,
    }

    if env.famille == "cc3000":
        cc = alim.get("cc") or {}
        cfg["r_cat"] = float(cc.get("r_cat", 0.05) or 0.05)
        cfg["r_rail"] = float(cc.get("r_rail", 0.015) or 0.015)
        cfg["g_re"] = float(cc.get("g_rail_terre", 0.2) or 0.2)

        cfg_sst = []
        for k, s in enumerate(sst_list):
            actif = (s.get("en_service") not in ("non", False)) and not hs.get(k, False)
            cfg_sst.append({
                "nom": s.get("nom", f"SST {k + 1}"),
                "x": env.coord.x(float(s.get("pk", 0.0))),
                "pk": float(s.get("pk", 0.0)),
                "u0": float(s.get("u0", 3600.0) or 3600.0),
                "r_int": float(s.get("r_int", 0.05) or 0.05),
                "p_nom": float(s.get("p_nom_kw", 0.0) or 0.0),
                "actif": actif,
            })
        cfg["sst"] = cfg_sst
        cfg["postes"] = [
            {
                "nom": p.get("nom", "PS"),
                "x": env.coord.x(float(p.get("pk", 0.0))),
                "pk": float(p.get("pk", 0.0)),
                "type": p.get("type", "PS"),
            }
            for p in postes_list
        ]
    else:
        ac = alim.get("ac") or {}
        u0 = float(ac.get("u0", 27500.0) or 27500.0)
        cfg["deux"] = (env.systeme == "ac2x25")
        cfg["zc"] = [float(ac.get("zc_r", 0.16) or 0.16), float(ac.get("zc_x", 0.45) or 0.45)]
        cfg["zf"] = [float(ac.get("zf_r", 0.12) or 0.12), float(ac.get("zf_x", 0.68) or 0.68)]
        cfg["zcf"] = [float(ac.get("zcf_r", 0.05) or 0.05), float(ac.get("zcf_x", 0.32) or 0.32)]

        sat = float(ac.get("s_at_mva", 10.0) or 10.0)
        uat = float(ac.get("ucc_at_pct", 1.0) or 1.0)
        zat = uat / 100.0 * u0 * u0 / (sat * 1e6)
        cfg["zat"] = [zat / 5.0, zat]

        pontage = ov.get("pontage") or {}
        cfg_sst = []
        for k, s in enumerate(sst_list):
            sn = float(s.get("s_nom_mva", 20.0) or 20.0)
            ucc = float(s.get("ucc_pct", 10.0) or 10.0)
            scc = float(s.get("scc_mva", 2000.0) or 2000.0)
            ztr = ucc / 100.0 * u0 * u0 / (sn * 1e6)
            znet = 2.0 * u0 * u0 / (scc * 1e6)
            z = ztr + znet
            actif = (s.get("en_service") not in ("non", False)) and not hs.get(k, False)
            cfg_sst.append({
                "nom": s.get("nom", f"SST {k + 1}"),
                "x": env.coord.x(float(s.get("pk", 0.0))),
                "pk": float(s.get("pk", 0.0)),
                "e": u0,
                "zr": z / 10.0,
                "zx": z,
                "s_nom": sn * 1000.0,
                "scc": scc,
                "actif": actif,
                "ponte": bool(pontage.get(k, False)),
            })
        cfg["sst"] = cfg_sst

        fermes = ov.get("sp_fermes") or {}
        cfg["postes"] = [
            {
                "nom": p.get("nom", "Poste"),
                "x": env.coord.x(float(p.get("pk", 0.0))),
                "pk": float(p.get("pk", 0.0)),
                "type": p.get("type", "SSP"),
                "ferme": bool(fermes.get(k, False)),
                "at": (p.get("at") != "non") if cfg["deux"] else False,
            }
            for k, p in enumerate(postes_list)
        ]

    return cfg


def build_configuration_n1(env: SimulationEnv, k_sst_out: int, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Configuration en situation dégradée N-1 (sous-station k hors service)."""
    ov = dict(override or {})
    hs = dict(ov.get("hors_service") or {})
    hs[k_sst_out] = True
    ov["hors_service"] = hs

    if env.famille != "cc3000":
        alim = env.P.get("alimentation") or {}
        sst_list = ov.get("sst") or alim.get("sst") or []
        postes_list = ov.get("postes") or alim.get("postes") or []

        x_out = float(sst_list[k_sst_out].get("pk", 0.0))
        gauche = -1
        droite = -1
        xg = -float("inf")
        xd = float("inf")

        for j, p in enumerate(postes_list):
            if p.get("type") != "SP":
                continue
            px = float(p.get("pk", 0.0))
            if px < x_out and px > xg:
                xg = px
                gauche = j
            if px > x_out and px < xd:
                xd = px
                droite = j

        sp_fermes = {}
        if gauche >= 0:
            sp_fermes[gauche] = True
        if droite >= 0:
            sp_fermes[droite] = True
        ov["sp_fermes"] = sp_fermes

        # SST d'extrémité : pontage direct
        if gauche < 0 or droite < 0:
            pontage = {}
            pontage[k_sst_out] = True
            ov["pontage"] = pontage

    return build_network_configuration(env, ov)


def calculer_profils_isoles(env: SimulationEnv, dt: float = 1.0) -> List[Dict[str, Any]]:
    """Profils de puissance sous tension nominale pour simulation découplée."""
    out = []
    for c in env.circ:
        m = Marche(env.troncons, env.trains[c["ref_train"]], c, {"dt": dt, "marge": env.marge, "vitesse_ligne": env.vligne})
        t_arr, pk_arr, v_arr, p_arr = [], [], [], []
        while not m.fini and m.t < 36000:
            step_rec = m.step()
            t_arr.append(step_rec["t"])
            pk_arr.append(step_rec["pk"])
            v_arr.append(step_rec["v"])
            p_arr.append(step_rec["p_kw"])
        out.append({"t": t_arr, "pk": pk_arr, "v": v_arr, "p": p_arr})
    return out


def simuler(env: SimulationEnv, opts: Optional[Dict[str, Any]] = None, prog_callback: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
    """Exécute une simulation temporelle pas-à-pas complète."""
    opts = opts or {}
    t0 = time.time()
    dt = float(opts.get("dt", 1.0) or 1.0)
    cfg = opts.get("cfg") or build_network_configuration(env)
    solve_fn = resoudre_cc if cfg["famille"] == "cc3000" else resoudre_ac
    prof = opts.get("profils")
    couplage = (not prof) and (opts.get("couplage") is not False)

    nt = int(env.duree / dt)
    ns = len(cfg["sst"])

    R: Dict[str, Any] = {
        "dt": dt,
        "nt": nt,
        "ns": ns,
        "famille": cfg["famille"],
        "couplage": couplage,
        "sst_p": np.zeros(nt * ns, dtype=np.float32),
        "sst_i": np.zeros(nt * ns, dtype=np.float32),
        "sst_u": np.zeros(nt * ns, dtype=np.float32),
        "sst_s": np.zeros(nt * ns, dtype=np.float32),
        "fd_g": np.zeros(nt * ns, dtype=np.float32),
        "fd_d": np.zeros(nt * ns, dtype=np.float32),
        "pertes_ligne": np.zeros(nt, dtype=np.float32),
        "pertes_sst": np.zeros(nt, dtype=np.float32),
        "rheostat": np.zeros(nt, dtype=np.float32),
        "circ": [
            {
                "id": c["id"],
                "nom": c["nom"],
                "ref": c["ref_train"],
                "sens": c["sens"],
                "voie": c["voie"],
                "depart_s": c["depart_s"],
                "t": [],
                "pk": [],
                "v": [],
                "pdem": [],
                "u": [],
                "i": [],
                "p": [],
                "vrail": [],
            }
            for c in env.circ
        ],
    }

    marches: Dict[int, Marche] = {}
    idx_prof: Dict[int, int] = {}
    u_prev: Dict[int, float] = {}
    next_circ = 0
    order = env.circ

    for it in range(nt):
        t_curr = (it + 1) * dt
        while next_circ < len(order) and order[next_circ]["depart_s"] < t_curr - 1e-9:
            c = order[next_circ]
            if prof:
                idx_prof[c["id"]] = 0
            else:
                marches[c["id"]] = Marche(env.troncons, env.trains[c["ref_train"]], c, {"dt": dt, "marge": env.marge, "vitesse_ligne": env.vligne})
            next_circ += 1

        charges: List[Dict[str, Any]] = []
        recs: Dict[int, Dict[str, Any]] = {}

        if prof:
            for c_id in list(idx_prof.keys()):
                pr = prof[c_id]
                k = idx_prof[c_id]
                if k >= len(pr["t"]):
                    del idx_prof[c_id]
                    continue
                recs[c_id] = {"pk": pr["pk"][k], "v": pr["v"][k], "p_kw": pr["p"][k], "kp": 1.0}
                idx_prof[c_id] = k + 1
        else:
            for c_id in list(marches.keys()):
                m = marches[c_id]
                if m.fini:
                    del marches[c_id]
                    continue
                tr = m.tr
                u_p = u_prev.get(c_id) if couplage else None
                # Derating en sous-tension
                kp = 1.0
                if couplage and u_p and tr.type != "serie_cc":
                    kp = max(0.0, limite_p(1.0, u_p, env.normes))
                rec = m.step(u_p if tr.type == "serie_cc" else None, kp)
                rec["kp"] = kp
                recs[c_id] = rec

        for c_id, r_info in recs.items():
            cc = env.circ[c_id]
            charges.append({
                "id": c_id,
                "voie": cc["voie"],
                "x": env.coord.x(float(r_info["pk"])),
                "p_kw": float(r_info["p_kw"]),
                "kp": float(r_info["kp"]),
                "cos_phi": float(env.trains[cc["ref_train"]].cos_phi),
            })

        offset = it * ns
        if charges:
            res_solve = solve_fn(cfg, charges, u_prev)
            for j in range(ns):
                R["sst_p"][offset + j] = res_solve["sst_p"][j]
                R["sst_i"][offset + j] = res_solve["sst_i"][j]
                R["sst_u"][offset + j] = res_solve["sst_u"][j]
                R["sst_s"][offset + j] = res_solve.get("sst_s", res_solve["sst_p"])[j]
                R["fd_g"][offset + j] = res_solve["fd_g"][j]
                R["fd_d"][offset + j] = res_solve["fd_d"][j]

            R["pertes_ligne"][it] = res_solve["pertes_ligne"]
            R["pertes_sst"][it] = res_solve["pertes_sst"]
            R["rheostat"][it] = res_solve["rheostat"]

            for q, ch in enumerate(charges):
                cid = ch["id"]
                rc = R["circ"][cid]
                rr = recs[cid]
                rc["t"].append(t_curr)
                rc["pk"].append(rr["pk"])
                rc["v"].append(rr["v"])
                rc["pdem"].append(rr["p_kw"])
                rc["u"].append(res_solve["u"][cid])
                rc["i"].append(res_solve["i"][cid])
                rc["p"].append(res_solve["p"][cid])
                rc["vrail"].append(res_solve["vrail"][cid])
                u_prev[cid] = res_solve["u"][cid]
        else:
            for j in range(ns):
                R["sst_u"][offset + j] = float(cfg["sst"][j].get("u0") or cfg["sst"][j].get("e", 0.0))

        if prog_callback and (it % 200 == 0 or it == nt - 1):
            prog_callback((it + 1) / nt, "Simulation en cours...")

    R["cfg"] = cfg
    R["duree_calcul"] = time.time() - t0
    return R


def analyser(env: SimulationEnv, R: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule l'ensemble des grandeurs synthétiques, bilans et conformités."""
    normes = env.normes
    dt = float(R["dt"])
    ns = int(R["ns"])
    nt = int(R["nt"])
    ac = (R["famille"] != "cc3000")

    w1 = max(1, int(round(60.0 / dt)))
    w10 = max(1, int(round(600.0 / dt)))
    w15 = max(1, int(round(900.0 / dt)))
    w60 = max(1, int(round(3600.0 / dt)))

    sst_stats = []
    for j, s in enumerate(R["cfg"]["sst"]):
        e = 0.0
        pmax = 0.0
        imax = 0.0
        smax = 0.0
        umin = float("inf")
        fgmax = 0.0
        fdmax = 0.0

        i2 = np.zeros(nt, dtype=np.float64)
        fg2 = np.zeros(nt, dtype=np.float64)
        fd2 = np.zeros(nt, dtype=np.float64)

        for it in range(nt):
            o = it * ns + j
            p = float(R["sst_p"][o])
            i_val = float(R["sst_i"][o])
            e += p * dt / 3600.0
            pmax = max(pmax, p)
            imax = max(imax, i_val)
            smax = max(smax, float(R["sst_s"][o]))
            if i_val > 0:
                umin = min(umin, float(R["sst_u"][o]))
            i2[it] = i_val * i_val
            fg2[it] = float(R["fd_g"][o]) ** 2
            fd2[it] = float(R["fd_d"][o]) ** 2
            fgmax = max(fgmax, abs(float(R["fd_g"][o])))
            fdmax = max(fdmax, abs(float(R["fd_d"][o])))

        s_10m = moy_max(R["sst_s"], j, ns, nt, w10)
        scc = float(s.get("scc", 0.0) or 0.0)
        deseq = (s_10m / 1000.0 / scc * 100.0) if (ac and scc > 0) else None

        p_1h = moy_max(R["sst_p"], j, ns, nt, w60)
        s_1h = moy_max(R["sst_s"], j, ns, nt, w60)

        sst_stats.append({
            "nom": s["nom"],
            "pk": float(s["pk"]),
            "actif": bool(s.get("actif")),
            "energie_kwh": e,
            "p_max": pmax,
            "i_max": imax,
            "s_max": smax,
            "p_1min": moy_max(R["sst_p"], j, ns, nt, w1),
            "p_15min": moy_max(R["sst_p"], j, ns, nt, w15),
            "p_1h": p_1h,
            "s_1min": moy_max(R["sst_s"], j, ns, nt, w1),
            "s_10min": s_10m,
            "s_15min": moy_max(R["sst_s"], j, ns, nt, w15),
            "s_1h": s_1h,
            "i_eff_15min": math.sqrt(moy_max(i2, 0, 1, nt, w15)),
            "i_eff_1h": math.sqrt(moy_max(i2, 0, 1, nt, w60)),
            "fd_g_max": fgmax,
            "fd_d_max": fdmax,
            "fd_eff_15min": math.sqrt(max(moy_max(fg2, 0, 1, nt, w15), moy_max(fd2, 0, 1, nt, w15))),
            "u_min": umin if math.isfinite(umin) else float(s.get("u0") or s.get("e", 0.0)),
            "p_nom": float(s.get("p_nom") or s.get("s_nom", 0.0)),
            "scc": scc,
            "charge": s_1h if ac else p_1h,
            "desequilibre_pct": deseq,
        })

    train_stats = []
    fin_sens1 = float(env.troncons[-1]["pk_fin"])
    fin_sens2 = float(env.troncons[0]["pk_ini"])

    for c in R["circ"]:
        if not c["t"]:
            continue
        umin = float("inf")
        kmin = 0
        su = 0.0
        nu = 0
        e_tr = 0.0
        rec = 0.0
        sous = 0.0
        vr_max = 0.0

        for k in range(len(c["u"])):
            u_k = float(c["u"][k])
            p_k = float(c["p"][k])
            if u_k < umin:
                umin = u_k
                kmin = k
            if float(c["pdem"][k]) > 0:
                su += u_k
                nu += 1
            if p_k > 0:
                e_tr += p_k * dt / 3600.0
            else:
                rec -= p_k * dt / 3600.0
            if u_k < float(normes.get("umin1", 2000.0)):
                sous += dt
            vr_max = max(vr_max, abs(float(c["vrail"][k])))

        fin = fin_sens1 if c["sens"] > 0 else fin_sens2
        train_stats.append({
            "id": c["id"],
            "nom": c["nom"],
            "train": env.trains[c["ref"]].nom,
            "sens": c["sens"],
            "voie": c["voie"],
            "depart_s": c["depart_s"],
            "duree_s": c["t"][-1] - c["depart_s"],
            "complet": abs(float(c["pk"][-1]) - fin) < 0.05,
            "energie_kwh": e_tr,
            "recup_kwh": rec,
            "u_min": umin,
            "pk_u_min": float(c["pk"][kmin]),
            "t_u_min": float(c["t"][kmin]),
            "u_moy_utile": (su / nu) if nu else float("nan"),
            "t_sous_umin1": sous,
            "v_rail_max": vr_max,
        })

    # Zones d'alimentation entre sous-stations
    pks_sst = sorted([float(s["pk"]) for s in R["cfg"]["sst"] if s.get("actif")])
    d0 = float(env.troncons[0]["pk_ini"])
    d1 = float(env.troncons[-1]["pk_fin"])
    bornes = [d0] + [x for x in pks_sst if d0 < x < d1] + [d1]

    zones = []
    for z in range(len(bornes) - 1):
        a_z = bornes[z]
        b_z = bornes[z + 1]
        su2 = 0.0
        nu2 = 0
        um = float("inf")
        for c in R["circ"]:
            for k in range(len(c["pk"])):
                pk_val = float(c["pk"][k])
                if a_z <= pk_val < b_z:
                    u_val = float(c["u"][k])
                    um = min(um, u_val)
                    if float(c["pdem"][k]) > 0:
                        su2 += u_val
                        nu2 += 1
        zones.append({
            "pk_debut": a_z,
            "pk_fin": b_z,
            "u_moy_utile": (su2 / nu2) if nu2 else float("nan"),
            "u_min": um if math.isfinite(um) else float("nan"),
            "n": nu2,
        })

    # Bilans globaux
    esst = sum(s["energie_kwh"] for s in sst_stats)
    pl = float(np.sum(R["pertes_ligne"]) * dt / 3600.0)
    psst = float(np.sum(R["pertes_sst"]) * dt / 3600.0)
    rh = float(np.sum(R["rheostat"]) * dt / 3600.0)
    etr = sum(t["energie_kwh"] for t in train_stats)
    erec = sum(t["recup_kwh"] for t in train_stats)

    umin_glob = min((t["u_min"] for t in train_stats), default=float("inf"))
    worst_train = min(train_stats, key=lambda t: t["u_min"]) if train_stats else None
    vrm_glob = max((t["v_rail_max"] for t in train_stats), default=0.0)
    umoy_zone_min = min((z["u_moy_utile"] for z in zones if z["n"] > 20), default=float("inf"))

    glob = {
        "energie_sst_kwh": esst,
        "energie_trains_kwh": etr - erec,
        "recup_kwh": erec,
        "pertes_ligne_kwh": pl,
        "pertes_sst_kwh": psst,
        "rheostat_kwh": rh,
        "rendement": ((etr - erec) / esst) if esst > 0 else float("nan"),
        "u_min": umin_glob,
        "pire": worst_train,
        "v_rail_max": vrm_glob,
        "u_moy_zone_min": umoy_zone_min,
        "nb_circ": len(train_stats),
        "duree_calcul": float(R["duree_calcul"]),
    }

    return {
        "sst": sst_stats,
        "trains": train_stats,
        "zones": zones,
        "glob": glob,
        "normes": normes,
        "famille": R["famille"],
    }


def verifications_normatives(analysis: Dict[str, Any], situation: str = "normale") -> List[Dict[str, Any]]:
    """Vérifie la conformité aux normes EN 50163, EN 50388-1, EN 50122-1 et EN 50160."""
    N = analysis["normes"]
    ac = (analysis["famille"] != "cc3000")
    g = analysis["glob"]
    deg = (situation != "normale")

    def kv_fmt(v: float) -> str:
        return f"{v / 1000.0:.2f} kV" if ac else f"{int(round(v))} V"

    out = []
    seuil_u = float(N.get("umin2") if deg else N.get("umin1"))
    out.append({
        "critere": "Tension minimale au pantographe",
        "norme": f"EN 50163 ({'Umin2' if deg else 'Umin1'})",
        "valeur": g["u_min"],
        "seuil": seuil_u,
        "ok": bool(g["u_min"] >= seuil_u),
        "txt": f"{kv_fmt(g['u_min'])} >= {kv_fmt(seuil_u)}",
    })

    su = float(N.get("umoy_zone_degrade") if deg else N.get("umoy_zone"))
    if math.isfinite(g["u_moy_zone_min"]):
        out.append({
            "critere": "Tension moyenne utile (zone la plus faible)",
            "norme": "EN 50388-1",
            "valeur": g["u_moy_zone_min"],
            "seuil": su,
            "ok": bool(g["u_moy_zone_min"] >= su),
            "txt": f"{kv_fmt(g['u_moy_zone_min'])} >= {kv_fmt(su)}",
        })

    if not ac and N.get("v_rail_max"):
        v_seuil = float(N["v_rail_max"])
        out.append({
            "critere": "Potentiel du rail (tension de contact)",
            "norme": "EN 50122-1",
            "valeur": g["v_rail_max"],
            "seuil": v_seuil,
            "ok": bool(g["v_rail_max"] <= v_seuil),
            "txt": f"{int(round(g['v_rail_max']))} V <= {int(v_seuil)} V",
            "indicatif": True,
        })

    if ac and N.get("desequilibre_max_pct"):
        d_seuil = float(N["desequilibre_max_pct"])
        for s in analysis["sst"]:
            if s.get("desequilibre_pct") is not None and s.get("actif"):
                val = float(s["desequilibre_pct"])
                out.append({
                    "critere": f"Déséquilibre de tension HT – {s['nom']}",
                    "norme": "EN 50160 / Gestionnaire HT",
                    "valeur": val,
                    "seuil": d_seuil,
                    "ok": bool(val <= d_seuil),
                    "txt": f"{val:.2f} % <= {d_seuil:.2f} %",
                })

    return out
