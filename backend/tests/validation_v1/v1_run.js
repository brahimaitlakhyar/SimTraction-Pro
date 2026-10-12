// Exécute le moteur JavaScript de SimTraction V1 sous Node, sur un projet de la BDD V1.
// Usage : node v1_run.js <dossier_V1> <projet> <dt> <sortie.json> [mode]
//   simulation (défaut) : situation normale, avec séries brutes
//   etude               : commande « simuler » du worker V1 (normale + N-1 + séries allégées)
//   dimensionner        : commande « dimensionner » (paramètres préparés comme paramsDim)
//   comparer            : commande « comparer » (une recherche par puissance unitaire)
const fs = require("fs"), path = require("path"), vm = require("vm");
const [V1, projet, dtArg, out, mode = "simulation"] = process.argv.slice(2);
const html = fs.readFileSync(path.join(V1, "SimTraction.html"), "utf8");

function bloc(ouverture) {           // contenu d'un <script> repéré par sa première ligne
  const i = html.indexOf(ouverture);
  if (i < 0) throw new Error("bloc introuvable : " + ouverture);
  const d = html.indexOf(">", i) + 1, f = html.indexOf("</script>", d);
  return html.slice(d, f);
}
function charger(src) {              // contexte isolé sans `module` → les scripts s'accrochent à self
  const ctx = vm.createContext({ console, Float32Array, Float64Array, Uint8Array, Int32Array, Date, Math, JSON });
  ctx.self = ctx;
  vm.runInContext(src, ctx);
  return ctx;
}

const ctxMoteur = charger(bloc('<script id="engine">')), ST = ctxMoteur.ST;
const B = charger(bloc("<script>/* ==========================================================================\n   SimTraction — base de données")).BDD;

const lire = (f, cols) => fs.existsSync(f) ? B.depuisCsv(fs.readFileSync(f, "utf8"), cols) : null;
const bdd = path.join(V1, "BDD"), dp = path.join(bdd, "projets", projet);

// Réplique de B.chargerProjet (lecture fs au lieu de l'API File System Access)
const r = ["parametres", "trace", "materiel", "trafic", "sous_stations", "postes", "sites"].map((n, k) =>
  lire(path.join(dp, n + ".csv"), [B.F.kv, B.F.trace, B.F.materiel, B.F.trafic, B.F.sst, B.F.postes, B.F.sites][k]));
const P = { trace: { troncons: r[1] || [] }, trains: r[2] || [], trafic: r[3] || [], normes: {},
            alimentation: { cc: {}, ac: {}, sst: r[4] || [], postes: r[5] || [] }, dimensionnement: { candidats: r[6] || [] } };
B.lignesVersParams(r[0], P);
P.id = projet;

// NORMES_BD comme dans l'application (parametres/normes.csv)
const NORMES_BD = {};
(lire(path.join(bdd, "parametres", "normes.csv"), B.F.normes) || []).forEach(n => {
  if (n.systeme && n.code && n.valeur !== "") (NORMES_BD[n.systeme] = NORMES_BD[n.systeme] || {})[n.code] = +n.valeur;
});
const projetCalc = Object.assign({}, P, { normesBase: NORMES_BD });

const dt = +dtArg || 5, t0 = Date.now();
const json = o => JSON.stringify(o, (k, v) => (typeof v === "number" && !isFinite(v)) ? String(v) : v);

if (mode === "etude") {
  vm.runInContext(bloc('<script type="text/plain" id="worker-src">'), ctxMoteur);
  let fin = null;
  ctxMoteur.STtraiter({ cmd: "simuler", projet: projetCalc, opts: { dt, couplage: true, n1: true } }, m => {
    if (m.type === "fin" || m.type === "erreur") fin = m;
  });
  if (!fin || fin.type === "erreur") throw new Error("Échec V1 : " + (fin && fin.message));
  fs.writeFileSync(out, json({ projet: P, etude: fin }));
  console.log(`V1 étude ${projet} dt=${dt}s : ${fin.n1.length} cas N-1, ${(Date.now() - t0) / 1000}s`);
  return;
}

if (mode === "dimensionner" || mode === "comparer") {
  // REGLAGES et paramsDim exactement comme l'interface V1 (parseNum, rendreDimForm, paramsDim)
  const parseNum = v => {
    if (v === "" || v == null) return "";
    const s = String(v).trim().replace(/ |\s/g, "").replace(",", ".");
    const n = Number(s);
    return isFinite(n) && s !== "" ? n : v;
  };
  const REGLAGES = {};
  (lire(path.join(bdd, "parametres", "reglages.csv"), B.F.kv) || []).forEach(x => { if (x.code) REGLAGES[x.code] = parseNum(x.valeur); });
  const reg = (code, defaut) => { const v = REGLAGES[code]; return v === "" || v == null ? (defaut == null ? "" : defaut) : v; };
  const ac = P.systeme !== "cc3000", sy = "dim." + P.systeme + ".";
  const champs = [["pas_min_km", reg(sy + "pas_min_km")], ["pas_max_km", reg(sy + "pas_max_km")],
    ["puissances", String(reg(sy + "puissances")).replace(/\//g, ";")], ["surcharge_n", reg("dim.surcharge_n")],
    ["surcharge_n1", reg("dim.surcharge_n1")], ["surcharge_pointe", reg(sy + "surcharge_pointe")],
    ["variantes", String(reg(sy + "variantes", ac ? "20000/40000" : "3000/6000")).replace(/\//g, ";")]];
  if (!ac) champs.push(["chute_pct", reg(sy + "chute_pct", 6)]);
  champs.push(ac ? ["pas_at_km", reg(sy + "pas_at_km")] : ["pas_ps_km", reg(sy + "pas_ps_km")]);
  const src = P.dimensionnement;
  champs.forEach(c => { src["_def_" + c[0]] = c[1]; });
  const D = {};
  Object.keys(src).forEach(k => { if (k.indexOf("_def_") !== 0) D[k] = src[k] === "" || src[k] == null ? src["_def_" + k] : src[k]; });
  ["pas_min_km", "pas_max_km", "puissances", "surcharge_n", "surcharge_n1", "surcharge_pointe", "pas_at_km", "pas_ps_km", "variantes", "chute_pct"]
    .forEach(k => { if (D[k] === "" || D[k] == null) D[k] = src["_def_" + k]; });
  D.n1 = src.n1 === "non" ? false : (src.n1 === "interm" ? "interm" : true); D.dt = +src.dt || 5;
  champs.forEach(c => { delete src["_def_" + c[0]]; });

  vm.runInContext(bloc('<script type="text/plain" id="worker-src">'), ctxMoteur);
  const logs = [];
  let fin = null;
  const msg = { cmd: mode, projet: projetCalc, D };
  if (mode === "comparer")
    msg.variantes = String(D.variantes || "").split(/[;\/\s]+/).map(x => +String(x).replace(",", "."))
      .filter(x => x > 0).filter((x, i, a) => a.indexOf(x) === i).sort((a, b) => a - b);
  ctxMoteur.STtraiter(msg, m => {
    if (m.type === "log") logs.push(m.txt);
    if (m.type === "fin" || m.type === "erreur") fin = m;
  });
  if (!fin || fin.type === "erreur") throw new Error("Échec V1 : " + (fin && fin.message));
  fs.writeFileSync(out, json({ projet: P, D, variantes: msg.variantes || null, logs, resultat: fin }));
  console.log(`V1 ${mode} ${projet} : ${(Date.now() - t0) / 1000}s`);
  return;
}

const E = ST.preparer(projetCalc);
const cfg = ST.configuration(E);
const R = ST.simuler(E, { cfg, couplage: true, dt });
const A = ST.analyser(E, R);
const conf = ST.verifications(E, A, "normale");

const arr = a => Array.from(a);
fs.writeFileSync(out, json({
  projet: P, normes: E.normes, duree_calcul: (Date.now() - t0) / 1000,
  nb_circ: E.circ.length, avert: E.avert,
  A: { glob: A.glob, sst: A.sst, trains: A.trains, zones: A.zones }, conf,
  R: { nt: R.nt, ns: R.ns, sst_p: arr(R.sst_p), sst_u: arr(R.sst_u), pertes_ligne: arr(R.pertes_ligne),
       circ: R.circ.map(c => ({ id: c.id, nom: c.nom, t: c.t, pk: c.pk, v: c.v, pdem: c.pdem, u: c.u, p: c.p })) },
}));
console.log(`V1 ${projet} dt=${dt}s : ${E.circ.length} circulations, u_min=${A.glob.u_min.toFixed(1)} V, ${(Date.now() - t0) / 1000}s`);
