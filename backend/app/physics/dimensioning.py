"""
Dimensionnement et implantation automatique des sous-stations de traction.
Transposition fidèle de ST.dimensionner (SimTraction V1), validée contre V1 exécuté sous Node :
- nombre minimal de sous-stations, puis renforcement successif du point faible (tension) ou de la
  sous-station surchargée (puissance unitaire imposée) ;
- vérification en situation normale et dégradée N-1 ;
- élagage des sous-stations superflues ;
- choix des calibres normalisés (groupes redresseurs en kW, transformateurs en kVA) ;
- comparaison de puissances unitaires imposées (ex. 3 MW / 6 MW, 20 / 40 MVA).
Les arrondis JavaScript (Math.round, toFixed) sont reproduits par jscompat.
"""

import math
import time
from typing import Any, Callable, Dict, List, Optional

from .jscompat import js_fixed, js_fixed_num, js_num, js_round, js_sign, js_str
from .simulation import (
    SimulationEnv,
    analyser,
    build_configuration_n1,
    build_network_configuration,
    calculer_profils_isoles,
    simuler,
)

Progression = Callable[[float], None]
Journal = Callable[[str], None]


def parametres_dimensionnement(P: Dict[str, Any], reglages: Dict[str, Any]) -> Dict[str, Any]:
    """
    Paramètres de la recherche (équivalent de paramsDim en V1) : valeurs du projet, et à défaut
    celles de reglages.csv propres au système (dim.<systeme>.*) ou communes (dim.*).
    """
    systeme = P.get("systeme") or "cc3000"
    ac = systeme != "cc3000"
    sy = f"dim.{systeme}."

    def reg(code: str, defaut: Any = None) -> Any:
        v = reglages.get(code)
        return ("" if defaut is None else defaut) if v in ("", None) else v

    defauts = {
        "pas_min_km": reg(sy + "pas_min_km"),
        "pas_max_km": reg(sy + "pas_max_km"),
        "puissances": str(reg(sy + "puissances")).replace("/", ";"),
        "surcharge_n": reg("dim.surcharge_n"),
        "surcharge_n1": reg("dim.surcharge_n1"),
        "surcharge_pointe": reg(sy + "surcharge_pointe"),
        "variantes": str(reg(sy + "variantes", "20000/40000" if ac else "3000/6000")).replace("/", ";"),
    }
    if not ac:
        defauts["chute_pct"] = reg(sy + "chute_pct", 6)
    if ac:
        defauts["pas_at_km"] = reg(sy + "pas_at_km")
    else:
        defauts["pas_ps_km"] = reg(sy + "pas_ps_km")

    src = dict(P.get("dimensionnement") or {})
    for k in ("puissances", "variantes"):  # séparateur « ; » comme à la lecture du CSV par V1
        if isinstance(src.get(k), str):
            src[k] = src[k].replace("/", ";")
    D: Dict[str, Any] = {}
    for k, v in src.items():
        D[k] = defauts.get(k) if v in ("", None) else v
    for k in ("pas_min_km", "pas_max_km", "puissances", "surcharge_n", "surcharge_n1", "surcharge_pointe",
              "pas_at_km", "pas_ps_km", "variantes", "chute_pct"):
        if D.get(k) in ("", None):
            D[k] = defauts.get(k)
    n1 = src.get("n1")
    D["n1"] = False if n1 == "non" else ("interm" if n1 == "interm" else True)
    D["dt"] = js_num(src.get("dt"), 0.0) or 5.0
    return D


def liste_variantes(D: Dict[str, Any]) -> List[float]:
    """Puissances unitaires à comparer (listeVariantes en V1) : uniques, croissantes."""
    out: List[float] = []
    for x in str(D.get("variantes") or "").replace("/", " ").replace(";", " ").split():
        v = js_num(x.replace(",", ".", 1), 0.0)
        if v > 0 and v not in out:
            out.append(v)
    return sorted(out)


def dimensionner(
    env: SimulationEnv,
    D: Optional[Dict[str, Any]] = None,
    progression: Optional[Progression] = None,
    log: Optional[Journal] = None,
) -> Dict[str, Any]:
    """Recherche automatique des sous-stations et des postes (ST.dimensionner)."""
    t0 = time.time()
    D = D or {}
    ac = env.famille != "cc3000"
    A0 = env.P.get("alimentation") or {}
    dt = js_num(D.get("dt"), 5.0)
    log = log or (lambda _m: None)
    progression = progression or (lambda _f: None)
    unite = "kVA" if ac else "kW"

    profils = calculer_profils_isoles(env, dt)
    d0 = float(env.troncons[0]["pk_ini"])
    d1 = float(env.troncons[-1]["pk_fin"])
    L = d1 - d0

    cands = [
        {"nom": c.get("nom") or ("Site PK " + js_str(js_num(c["pk"], 0.0))),
         "pk": js_num(c["pk"], 0.0), "scc_mva": js_num(c.get("scc_mva"), 2000.0)}
        for c in (D.get("candidats") or [])
        if c.get("pk") not in ("", None)
    ]
    cands.sort(key=lambda c: c["pk"])

    pas_max = js_num(D.get("pas_max_km"), 60.0 if ac else 25.0)
    pas_min = js_num(D.get("pas_min_km"), 25.0 if ac else 8.0)
    brut = D.get("puissances")
    elems = brut if isinstance(brut, list) else str(brut or "").replace(";", " ").split()
    std = sorted(v for v in (js_num(str(x).replace(",", ".", 1), 0.0) for x in elems) if v > 0)
    sN = js_num(D.get("surcharge_n"), 1.0)
    sN1 = js_num(D.get("surcharge_n1"), 1.5)
    sP = js_num(D.get("surcharge_pointe"), 2.0 if ac else 3.0)
    tmpl = (A0.get("sst") or [{}])[0] if A0.get("sst") else {}

    # Puissance unitaire imposée (variante « toutes les sous-stations à X kW / kVA »)
    pU = js_num(str("" if D.get("p_unite") is None else D.get("p_unite")).replace(",", ".", 1), 0.0)
    if pU > 0:
        std = [pU]
    u0cc = js_num(tmpl.get("u0"), 3600.0)
    chute = js_num(str("" if D.get("chute_pct") is None else D.get("chute_pct")).replace(",", ".", 1), 6.0)
    un = js_num(env.normes.get("un"), 3000.0)

    def r_int_pour(p: float) -> float:
        inom = p * 1000.0 / un
        return js_fixed_num(chute / 100.0 * u0cc / inom, 4)

    def sst_at(pk: float, nom: str, scc: Optional[float] = None) -> Dict[str, Any]:
        if ac:
            return {"nom": nom, "pk": js_fixed_num(pk, 3), "s_nom_mva": std[-1] / 1000.0 if std else 40.0,
                    "ucc_pct": js_num(tmpl.get("ucc_pct"), 10.0),
                    "scc_mva": scc if scc else js_num(tmpl.get("scc_mva"), 2000.0),
                    "u0": js_num((A0.get("ac") or {}).get("u0"), 27500.0), "en_service": "oui"}
        return {"nom": nom, "pk": js_fixed_num(pk, 3), "u0": u0cc,
                "r_int": r_int_pour(pU) if pU > 0 else js_num(tmpl.get("r_int"), 0.05),
                "p_nom_kw": std[-1] if std else 9000.0, "en_service": "oui"}

    def postes_pour(pks: List[float]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        s = sorted(pks)
        if ac:
            deux = env.P.get("systeme") == "ac2x25"
            pas_at = js_num(D.get("pas_at_km"), 15.0 if deux else 20.0)
            for i in range(len(s) - 1):
                xm = (s[i] + s[i + 1]) / 2.0
                out.append({"nom": "SP PK " + js_fixed(xm, 1), "pk": js_fixed_num(xm, 3), "type": "SP"})
            # SSP / ATS entre chaque SST et les SP (ou les extrémités)
            marks = [d0]
            for i, x in enumerate(s):
                marks.append(x)
                if i < len(s) - 1:
                    marks.append((x + s[i + 1]) / 2.0)
            marks.append(d1)
            typ = "ATS" if deux else "SSP"
            for j in range(len(marks) - 1):
                a, b = marks[j], marks[j + 1]
                k = math.ceil((b - a) / pas_at)
                for q in range(1, k):
                    x = a + (b - a) * q / k
                    out.append({"nom": f"{typ} PK " + js_fixed(x, 1), "pk": js_fixed_num(x, 3), "type": typ})
        else:
            pas_ps = js_num(D.get("pas_ps_km"), 10.0)
            for i in range(len(s) - 1):
                if s[i + 1] - s[i] > pas_ps:
                    xm = (s[i] + s[i + 1]) / 2.0
                    out.append({"nom": "PS PK " + js_fixed(xm, 1), "pk": js_fixed_num(xm, 3), "type": "PS"})
        out.sort(key=lambda p: p["pk"])
        return out

    def capacite(A: Dict[str, Any], deg: bool, sst_l: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Taux de charge à puissance imposée et position du renfort (milieu de l'intervalle le plus chargé)."""
        if not pU > 0:
            return None
        pire = None
        pks = [s["pk"] for s in sst_l]
        for k, s in enumerate(A["sst"]):
            if not s["actif"]:
                continue
            pointe = s["s_1min"] if ac else s["p_1min"]
            taux = max(s["charge"] / ((sN1 if deg else sN) * pU), pointe / (sP * pU))
            if pire is None or taux > pire["taux"]:
                pire = {"k": k, "taux": taux, "nom": s["nom"], "s": s}
        if pire is None:
            return None
        x = pks[pire["k"]]
        gauche = pire["s"]["fd_g_max"] >= pire["s"]["fd_d_max"]
        voisins = [p for j, p in enumerate(pks) if j != pire["k"]]
        g = max([d0] + [p for p in voisins if p < x])
        d = min([d1] + [p for p in voisins if p > x])
        pk = (g + x) / 2.0 if gauche else (x + d) / 2.0
        return {"marge": 1.0 - pire["taux"], "taux": pire["taux"], "nom": pire["nom"], "pk": pk}

    def evaluer(sst_l: List[Dict[str, Any]], postes: List[Dict[str, Any]], avec_n1: bool) -> Dict[str, Any]:
        cas: List[Dict[str, Any]] = [{"nom": "normale", "k": None, "ov": {"sst": sst_l, "postes": postes}}]
        if avec_n1:
            for k, s in enumerate(sst_l):
                if n1_interm and len(sst_l) > 2 and (k == 0 or k == len(sst_l) - 1):
                    continue  # extrémités doublées (2 groupes / 2 arrivées HT)
                cas.append({"nom": "N-1 " + s["nom"], "k": k, "ov": {"sst": sst_l, "postes": postes}})
        out: Dict[str, Any] = {"cas": [], "ok": True, "marge": math.inf, "pire": None,
                               "marge_cap": math.inf, "pire_cap": None}
        N = env.normes
        for c in cas:
            cfg = build_network_configuration(env, c["ov"]) if c["k"] is None else build_configuration_n1(env, c["k"], c["ov"])
            A = analyser(env, simuler(env, {"cfg": cfg, "profils": profils, "dt": dt}))
            deg = c["k"] is not None
            su = N["umin2"] if deg else N["umin1"]
            sz = N["umoy_zone_degrade"] if deg else N["umoy_zone"]
            m1 = (A["glob"]["u_min"] - su) / N["un"]
            m2 = (A["glob"]["u_moy_zone_min"] - sz) / N["un"] if math.isfinite(A["glob"]["u_moy_zone_min"]) else 1.0
            marge = min(m1, m2)
            cap = capacite(A, deg, sst_l)
            out["cas"].append({"nom": c["nom"], "k": c["k"], "A": A, "marge": marge,
                               "marge_cap": cap["marge"] if cap else None})
            if marge < out["marge"]:
                pire = A["glob"]["pire"]
                out["marge"] = marge
                out["pire"] = {"cas": c["nom"], "k": c["k"], "pk": pire["pk_u_min"] if pire else None}
            if cap and cap["marge"] < out["marge_cap"]:
                out["marge_cap"] = cap["marge"]
                out["pire_cap"] = {"cas": c["nom"], "pk": cap["pk"], "nom": cap["nom"], "taux": cap["taux"]}
        out["ok_u"] = out["marge"] >= 0
        out["ok_cap"] = not (out["marge_cap"] < 0)
        out["ok"] = out["ok_u"] and out["ok_cap"]
        # point faible à renforcer : la tension d'abord, sinon la sous-station surchargée
        if out["ok_u"] and not out["ok_cap"]:
            pc = out["pire_cap"]
            out["pire"] = {"cas": pc["cas"], "pk": pc["pk"], "cap": True, "nom": pc["nom"]}
        return out

    def placer(n: int) -> List[Any]:
        if n == 1:
            pks = [d0 + L / 2.0]
        else:  # extrémités à un quart d'intervalle des terminus (antenne courte en N-1)
            a = min(L / (n - 1 + 0.5) * 0.25, L / 4.0)
            sp = (L - 2.0 * a) / (n - 1)
            pks = [d0 + a + sp * i for i in range(n)]
        if not cands:
            return [js_round(x * 2.0) / 2.0 for x in pks]
        used, out = set(), []
        for x in pks:
            best, bd = -1, math.inf
            for j, c in enumerate(cands):
                if j not in used and abs(c["pk"] - x) < bd:
                    bd, best = abs(c["pk"] - x), j
            if best >= 0:
                used.add(best)
                out.append(best)
        return sorted(out)

    def liste_sst(pos: List[Any]) -> List[Dict[str, Any]]:
        out = []
        for i, p in enumerate(pos):
            if cands:
                c = cands[p]
                out.append(sst_at(c["pk"], c["nom"], c["scc_mva"]))
            else:
                out.append(sst_at(p, f"SST {i + 1} (PK " + js_fixed(p, 1) + ")"))
        return out

    n_min = max(1, math.ceil(L / pas_max))
    n_max = max(n_min, math.ceil(L / pas_min) + 2)
    if cands:
        n_max = min(n_max, len(cands))
    avec_n1 = D.get("n1") is not False and D.get("n1") != "non"
    n1_interm = D.get("n1") == "interm"
    essais: List[Dict[str, Any]] = []
    vus: Dict[tuple, int] = {}

    def cle(pos: List[Any]) -> tuple:
        return tuple(sorted(pos))

    def eval_pos(pos: List[Any], n1: bool) -> Dict[str, Any]:
        sl = liste_sst(pos)
        pst = postes_pour([s["pk"] for s in sl])
        return {"pos": list(pos), "sl": sl, "pst": pst, "ev": evaluer(sl, pst, n1)}

    def inserer(pos: List[Any], xw: float, k_out: Optional[int]) -> Optional[List[Any]]:
        """Nouvelle sous-station au point faible."""
        if cands:
            best, bd = -1, math.inf
            for j, c in enumerate(cands):
                if j not in pos and abs(c["pk"] - xw) < bd:
                    bd, best = abs(c["pk"] - xw), j
            if best < 0:
                return None
            return sorted(pos + [best])

        x = js_round(min(max(xw, d0), d1) * 2.0) / 2.0

        def trop(y: float) -> bool:  # trop près d'une sous-station existante
            return any(abs(p - y) < pas_min - 1e-6 for p in pos)

        if trop(x):
            # rapprocher du point faible la sous-station voisine la plus proche (hors celle hors service
            # dans la situation dimensionnante), sans descendre sous la distance minimale
            tri = sorted(pos)
            ordre = sorted((j for j in range(len(tri)) if j != k_out), key=lambda j: abs(tri[j] - xw))[:2]
            if k_out is not None and k_out < len(tri):
                ordre.append(k_out)  # en dernier recours : la sous-station hors service elle-même
            for j0 in ordre:
                p0 = tri[j0]
                autres = [p for j, p in enumerate(tri) if j != j0]
                lo = max([d0] + [p + pas_min for p in autres if p < p0])
                hi = min([d1] + [p - pas_min for p in autres if p > p0])
                y = js_round((p0 + (xw - p0) / 2.0) * 2.0) / 2.0
                if abs(y - p0) < 0.5:
                    y = js_round(xw * 2.0) / 2.0
                y = min(max(y, math.ceil(lo * 2.0) / 2.0), math.floor(hi * 2.0) / 2.0)
                if lo <= hi and abs(y - p0) >= 0.5 and js_sign(y - p0) == js_sign(xw - p0):
                    np2 = sorted(autres + [y])
                    if not vus.get(cle(np2)):
                        log("Sous-station du PK " + js_fixed(p0, 1) + " déplacée au PK " + js_fixed(y, 1)
                            + " (distance minimale " + js_str(pas_min) + " km)")
                        return np2

        if trop(x):  # milieu de l'intervalle contenant le point faible, puis intervalles voisins
            bornes = sorted(pos + [d0, d1])
            essais_x = []
            for q in range(len(bornes) - 1):
                a, b = bornes[q], bornes[q + 1]
                dist = 0.0 if a <= xw <= b else min(abs(xw - a), abs(xw - b))
                essais_x.append({"x": js_round(a + b) / 2.0, "d": dist})
            essais_x.sort(key=lambda e: e["d"])
            x = None
            for e in essais_x:
                if not trop(e["x"]) and e["d"] <= pas_max:
                    x = e["x"]
                    break
            if x is None:
                return None
        return sorted(pos + [x])

    def pct(v: float, d: int) -> str:
        return js_fixed(v * 100.0, d)

    pos = placer(n_min)
    etat = None
    dernier_echec = ""
    ins_cap = 0
    tour = 0
    while tour < 150:
        progression(min(0.9, tour / 40.0))
        r = eval_pos(pos, False)
        ev = r["ev"]
        msg = f"{len(pos)} SST : situation normale, marge de tension {pct(ev['marge'], 1)} %"
        if pU > 0:
            msg += f", taux de charge max {js_fixed((1.0 - ev['marge_cap']) * 100.0, 0)} %"
        if not ev["ok"]:
            msg += (" – " + ev["pire"]["nom"] + " surchargée, renfort vers PK " if ev["pire"].get("cap") else " – point faible PK ") \
                + js_fixed(ev["pire"]["pk"] or 0.0, 1)
        log(msg)
        essais.append({"n": len(pos), "pks": [s["pk"] for s in r["sl"]], "marge": ev["marge"], "pire": ev["pire"]})

        if tour == 0 and pU > 0:  # puissance imposée : nombre minimal pour porter la charge horaire totale
            tot = sum(s["charge"] for s in ev["cas"][0]["A"]["sst"])
            nc = math.ceil(tot / (sN * pU) - 1e-9)
            if len(pos) < nc <= n_max:
                ins_cap += nc - len(pos)
                log(f"Charge horaire totale {js_str(js_round(tot))} {unite} : au moins {nc} sous-stations de "
                    f"{js_str(js_round(pU))} {unite}")
                pos = placer(nc)
                vus[cle(pos)] = 1
                tour += 1
                continue

        if ev["ok"] and avec_n1:
            r1 = eval_pos(pos, True)
            essais[-1]["marge_n1"] = r1["ev"]["marge"]
            msg = f"{len(pos)} SST : critère N-1, marge de tension {pct(r1['ev']['marge'], 1)} %"
            if pU > 0:
                msg += f", taux de charge max {js_fixed((1.0 - r1['ev']['marge_cap']) * 100.0, 0)} %"
            log(msg + f" ({r1['ev']['pire']['cas']})")
            if r1["ev"]["ok"]:
                etat = r1
                break
            r = r1
            ev = r1["ev"]
        elif ev["ok"]:
            etat = r
            break

        pire = ev["pire"]
        if pire and pire.get("cap"):
            dernier_echec = f"{pire['nom']} chargée à {js_str(js_round((1.0 - ev['marge_cap']) * 100.0))} % ({pire['cas']})"
        else:
            dernier_echec = f"« {pire['cas']} », marge de tension {pct(ev['marge'], 1).replace('.', ',')} %" + (
                " au PK " + js_fixed(pire["pk"], 1).replace(".", ",") if pire["pk"] is not None else "")
        if len(pos) >= n_max:
            break
        np_pos = inserer(pos, pire["pk"] if pire["pk"] is not None else (d0 + d1) / 2.0, pire.get("k"))
        if not np_pos or vus.get(cle(np_pos)):
            break
        if pire.get("cap") and len(np_pos) > len(pos):
            ins_cap += 1
        vus[cle(np_pos)] = 1
        pos = np_pos
        tour += 1

    retenu = None
    if etat:
        # élagage : on retire les sous-stations superflues tant que les critères restent satisfaits
        change = True
        while change and len(etat["pos"]) > 1:
            change = False
            charges = [s["charge"] for s in etat["ev"]["cas"][0]["A"]["sst"]]
            ordre = sorted(range(len(etat["pos"])), key=lambda k: charges[k])
            for k_or in ordre:
                cand = [p for k, p in enumerate(etat["pos"]) if k != k_or]
                rr = eval_pos(cand, False)
                if not rr["ev"]["ok"]:
                    continue
                if avec_n1:
                    rr = eval_pos(cand, True)
                    if not rr["ev"]["ok"]:
                        continue
                log("Élagage : " + etat["sl"][k_or]["nom"] + " n'est pas nécessaire")
                etat = rr
                change = True
                break
        retenu = etat

    if not retenu:
        return {
            "ok": False, "essais": essais, "duree": time.time() - t0, "p_unite": pU or None,
            "message": "Aucune solution trouvée"
                       + (f" avec des sous-stations de {js_str(js_round(pU))} {unite}" if pU > 0 else "")
                       + f" (jusqu'à {n_max} sous-stations, distance minimale {js_str(pas_min)} km). "
                       + (f"Situation la plus défavorable au dernier essai : {dernier_echec}. " if dernier_echec else "")
                       + "Réduire la distance minimale, ajouter des sites candidats, "
                       + ("choisir une puissance unitaire plus forte, " if pU > 0 else "")
                       + "ou revoir le trafic et les seuils.",
        }

    # Puissances : charge horaire en N, en N-1 et pointe 1 min
    besoins = []
    for k, s in enumerate(retenu["sl"]):
        nrm = retenu["ev"]["cas"][0]["A"]["sst"][k]
        cN = nrm["charge"]
        cP = nrm["s_1min"] if ac else nrm["p_1min"]
        cN1, cas_n1 = 0.0, ""
        for c in retenu["ev"]["cas"][1:]:
            x = c["A"]["sst"][k]
            if not x["actif"]:
                continue
            if x["charge"] > cN1:
                cN1, cas_n1 = x["charge"], c["nom"]
            cP = max(cP, x["s_1min"] if ac else x["p_1min"])
        req = max(cN / sN, cN1 / sN1, cP / sP)
        if pU > 0:
            choix = pU
        else:
            sup = [p for p in std if p >= req]
            choix = sup[0] if sup else (None if std else math.ceil(req / 500.0) * 500.0)
        besoins.append({"nom": s["nom"], "pk": s["pk"], "charge_n": cN, "charge_n1": cN1, "cas_n1": cas_n1,
                        "pointe": cP, "requis": req, "choix": choix, "taux": req / choix if choix else None,
                        "desequilibre_pct": nrm.get("desequilibre_pct"), "scc": s.get("scc_mva")})

    for k, s in enumerate(retenu["sl"]):
        if ac:
            s["s_nom_mva"] = besoins[k]["choix"] / 1000.0 if besoins[k]["choix"] else s["s_nom_mva"]
        else:
            s["p_nom_kw"] = besoins[k]["choix"] or s["p_nom_kw"]

    progression(1.0)
    gN = retenu["ev"]["cas"][0]["A"]["glob"]
    return {
        "ok": True, "n": len(retenu["sl"]), "sst": retenu["sl"], "postes": retenu["pst"], "besoins": besoins,
        # situations évaluées, sans les analyses complètes (équivalent d'alleger() en V1)
        "cas": [{"nom": c["nom"], "marge": c["marge"], "marge_cap": c["marge_cap"],
                 "u_min": c["A"]["glob"]["u_min"], "u_moy": c["A"]["glob"]["u_moy_zone_min"]}
                for c in retenu["ev"]["cas"]],
        "essais": essais, "duree": time.time() - t0, "dt": dt, "p_unite": pU or None, "l_km": L, "d0": d0, "d1": d1,
        "pertes_kwh": gN["pertes_ligne_kwh"] + gN["pertes_sst_kwh"], "energie_kwh": gN["energie_sst_kwh"],
        "ajouts_capacite": ins_cap, "n1": ("interm" if n1_interm else True) if avec_n1 else False,
        "taux_max": max(b["requis"] / b["choix"] if b["choix"] else 0.0 for b in besoins),
    }


def comparer_variantes(
    env: SimulationEnv,
    variantes: List[float],
    D: Optional[Dict[str, Any]] = None,
    progression: Optional[Progression] = None,
    log: Optional[Journal] = None,
) -> List[Dict[str, Any]]:
    """Une recherche complète par puissance unitaire imposée (commande « comparer » du worker V1)."""
    log = log or (lambda _m: None)
    progression = progression or (lambda _f: None)
    unite = "kVA" if env.famille != "cc3000" else "kW"
    out = []
    for i, pu in enumerate(variantes):
        D2 = {**(D or {}), "p_unite": pu}
        log(f"=== Variante {i + 1} : sous-stations de {js_str(js_round(pu))} {unite} ===")
        r = dimensionner(env, D2, lambda f, i=i: progression((i + f) / len(variantes)), lambda t: log("  " + t))
        r["D"] = D2
        out.append(r)
        log(f"  → {r['n']} sous-stations, {len(r['postes'])} postes" if r["ok"] else "  → " + r["message"])
    return out
