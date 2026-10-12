// Exécute le moteur JavaScript de SimTraction V1 sous Node, sur un projet de la BDD V1.
// Usage : node v1_run.js <dossier_V1> <projet> <dt> <sortie.json>
const fs = require("fs"), path = require("path"), vm = require("vm");
const [V1, projet, dtArg, out] = process.argv.slice(2);
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

const ST = charger(bloc('<script id="engine">')).ST;
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
const E = ST.preparer(projetCalc);
const cfg = ST.configuration(E);
const R = ST.simuler(E, { cfg, couplage: true, dt });
const A = ST.analyser(E, R);
const conf = ST.verifications(E, A, "normale");

const arr = a => Array.from(a);
fs.writeFileSync(out, JSON.stringify({
  projet: P, normes: E.normes, duree_calcul: (Date.now() - t0) / 1000,
  nb_circ: E.circ.length, avert: E.avert,
  A: { glob: A.glob, sst: A.sst, trains: A.trains, zones: A.zones }, conf,
  R: { nt: R.nt, ns: R.ns, sst_p: arr(R.sst_p), sst_u: arr(R.sst_u), pertes_ligne: arr(R.pertes_ligne),
       circ: R.circ.map(c => ({ id: c.id, nom: c.nom, t: c.t, pk: c.pk, v: c.v, pdem: c.pdem, u: c.u, p: c.p })) },
}, (k, v) => (typeof v === "number" && !isFinite(v)) ? String(v) : v));
console.log(`V1 ${projet} dt=${dt}s : ${E.circ.length} circulations, u_min=${A.glob.u_min.toFixed(1)} V, ${(Date.now() - t0) / 1000}s`);
