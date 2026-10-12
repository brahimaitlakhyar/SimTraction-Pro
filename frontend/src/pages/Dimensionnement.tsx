import { useEffect, useMemo, useRef, useState } from "react";
import type { EChartsOption } from "echarts";
import { AlertTriangle, CheckCircle2, GitCompare, ListTree, Loader2, MapPinned, Ruler, ShieldCheck } from "lucide-react";
import {
  getDimParametres, getDimResult, getDimStatus, getProjects, getSimResult, getSimStatus,
  messageErreur, runDimensionnement, runSimulation,
} from "../api/client";
import {
  SYSTEM_LABELS, type DimParametres, type DimResultat, type DimSortie, type EtudeResultat, type Project,
  type SimulationTask, type SystemType, type TacheSuivie,
} from "../types";
import EChart from "../components/EChart";
import { CHART_COLORS as C, styledAxis } from "../components/chartTheme";
import ResultatsEtude from "../components/ResultatsEtude";
import { useTache } from "../hooks/useTache";
import { fmt, fmtE, fmtU } from "../utils/format";

interface Champ { cle: string; label: string; texte?: boolean }

function champs(systeme: SystemType): Champ[] {
  const ac = systeme !== "cc3000";
  const u = ac ? "kVA" : "kW";
  const out: Champ[] = [
    { cle: "pas_min_km", label: "Distance minimale entre SST (km)" },
    { cle: "pas_max_km", label: "Distance maximale entre SST (km)" },
    { cle: "puissances", label: `Puissances normalisées (${u}, séparées par ;)`, texte: true },
    { cle: "surcharge_n", label: "Charge horaire admise en N (× nominale)" },
    { cle: "surcharge_n1", label: "Surcharge horaire admise en N-1 (× nominale)" },
    { cle: "surcharge_pointe", label: "Pointe 1 min admise (× nominale)" },
    { cle: "variantes", label: `Puissances unitaires à comparer (${u}, séparées par ;)`, texte: true },
  ];
  if (ac) out.push({ cle: "pas_at_km", label: systeme === "ac2x25" ? "Distance max entre autotransformateurs (km)" : "Distance max entre postes de parallèle (km)" });
  else {
    out.push({ cle: "chute_pct", label: "Chute de tension interne d'un groupe à In (%)" });
    out.push({ cle: "pas_ps_km", label: "Placer un PS entre SST distantes de plus de (km)" });
  }
  return out;
}

/** Valeur saisie → valeur envoyée à l'API (virgule décimale admise). */
function versApi(v: unknown, texte?: boolean): string | number | null {
  const s = String(v ?? "").trim();
  if (s === "") return null;
  if (texte) return s;
  const n = Number(s.replace(",", "."));
  return Number.isFinite(n) ? n : s;
}

/** Valeur affichée dans un champ : nombres avec virgule décimale. */
const affichage = (v: unknown) => (typeof v === "number" ? String(v).replace(".", ",") : String(v ?? ""));

const libP = (p: number | null | undefined, ac: boolean) => (p ? `${fmt(p)} ${ac ? "kVA" : "kW"}` : "hors gamme");

export default function Dimensionnement() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [params, setParams] = useState<DimParametres>({});
  const [systeme, setSysteme] = useState<SystemType>("cc3000");
  const [nbSites, setNbSites] = useState(0);
  const [erreurChargement, setErreurChargement] = useState<string | null>(null);
  const [choix, setChoix] = useState(-1);
  const journalRef = useRef<HTMLPreElement>(null);

  const dim = useTache<TacheSuivie, DimSortie>({ statut: getDimStatus, resultat: getDimResult, memoriser: "simtraction.dim" });

  // Recherche reprise après un rechargement : revenir sur son projet
  const repris = useRef(false);
  useEffect(() => {
    if (!dim.suivi || repris.current) return;
    repris.current = true;
    setProjectId(dim.suivi.project_id);
  }, [dim.suivi]);

  useEffect(() => {
    getProjects()
      .then(ps => { setProjects(ps); setProjectId(id => id || ps[0]?.id || ""); })
      .catch(e => setErreurChargement(messageErreur(e)));
  }, []);

  useEffect(() => {
    if (!projectId) return;
    getDimParametres(projectId)
      .then(d => { setParams(d.parametres); setSysteme(d.systeme); setNbSites(d.candidats.length); })
      .catch(e => setErreurChargement(messageErreur(e)));
  }, [projectId]);

  useEffect(() => {
    if (journalRef.current) journalRef.current.scrollTop = journalRef.current.scrollHeight;
  }, [dim.suivi?.journal?.length]);

  useEffect(() => {
    // comparaison terminée : afficher la meilleure variante conforme (moins de SST, puis moins de pertes)
    if (dim.resultat?.mode === "comparer") {
      const vs = dim.resultat.variantes;
      let best = -1;
      vs.forEach((v, i) => {
        if (!v.ok) return;
        const b = vs[best];
        if (best < 0 || v.n < b.n || (v.n === b.n && v.pertes_kwh < b.pertes_kwh)) best = i;
      });
      setChoix(best);
    }
  }, [dim.resultat]);

  const ac = systeme !== "cc3000";
  const lancer = (mode: "dimensionner" | "comparer") => {
    const p: DimParametres = { n1: params.n1 ?? true, dt: params.dt ?? 5 };
    for (const c of champs(systeme)) p[c.cle] = versApi(params[c.cle], c.texte);
    setChoix(-1);
    repris.current = true;
    dim.lancer(() => runDimensionnement({ project_id: projectId, mode, parametres: p }));
  };

  const projet = projects.find(p => p.id === projectId);
  const solution: DimResultat | null =
    dim.resultat?.mode === "dimensionner" ? dim.resultat.resultat
      : dim.resultat?.mode === "comparer" && choix >= 0 ? dim.resultat.variantes[choix] : null;

  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Dimensionnement automatique</h1>
        <p>Implantation des sous-stations et des postes, calibres normalisés, critère N-1 et comparaison des puissances unitaires</p>
      </div>

      {erreurChargement && (
        <div className="card" style={{ display: "flex", gap: 12, color: "var(--clr-danger)", marginBottom: "var(--sp-md)" }}>
          <AlertTriangle size={20} /> {erreurChargement}
        </div>
      )}

      <div className="card" style={{ marginBottom: "var(--sp-lg)" }}>
        <div className="card-title"><Ruler size={16} /> Paramètres de la recherche</div>
        <hr className="divider" />
        <div className="dim-champs">
          <div className="form-group">
            <label className="form-label">Projet</label>
            <select className="form-input" value={projectId} onChange={e => setProjectId(e.target.value)}>
              {projects.map(p => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
            {projet && (
              <div style={{ fontSize: "0.75rem", color: "var(--clr-muted)", marginTop: 6 }}>
                {SYSTEM_LABELS[projet.systeme]} · {fmt(projet.longueur_km, 1)} km · {projet.nb_circulations} circulations ·{" "}
                {nbSites ? `${nbSites} sites HT candidats` : "implantation libre (aucun site candidat)"}
              </div>
            )}
          </div>
          {champs(systeme).map(c => (
            <div key={c.cle} className="form-group">
              <label className="form-label">{c.label}</label>
              <input className="form-input" value={affichage(params[c.cle])}
                onChange={e => setParams(p => ({ ...p, [c.cle]: e.target.value }))} />
            </div>
          ))}
          <div className="form-group">
            <label className="form-label">Critère N-1</label>
            <select className="form-input" value={String(params.n1 ?? true)}
              onChange={e => setParams(p => ({ ...p, n1: e.target.value === "interm" ? "interm" : e.target.value === "true" }))}>
              <option value="true">Chaque SST hors service doit rester conforme</option>
              <option value="interm">SST intermédiaires seulement (extrémités doublées)</option>
              <option value="false">Pas de critère N-1</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Pas de temps de la recherche</label>
            <select className="form-input" value={String(params.dt ?? 5)} onChange={e => setParams(p => ({ ...p, dt: +e.target.value }))}>
              {[2, 5, 10].map(d => <option key={d} value={d}>{d} s</option>)}
            </select>
          </div>
        </div>
        <div style={{ display: "flex", gap: "var(--sp-md)", flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={() => lancer("dimensionner")} disabled={dim.etat === "running" || !projectId}>
            {dim.etat === "running" ? <Loader2 size={16} className="spin" /> : <MapPinned size={16} />} Dimensionner
          </button>
          <button className="btn btn-ghost" onClick={() => lancer("comparer")} disabled={dim.etat === "running" || !projectId}>
            <GitCompare size={16} /> Comparer les puissances unitaires
          </button>
        </div>
      </div>

      {(dim.etat === "running" || (dim.suivi?.journal?.length ?? 0) > 0) && (
        <div className="card" style={{ marginBottom: "var(--sp-lg)" }}>
          <div className="card-title">
            {dim.etat === "running" ? <Loader2 size={16} className="spin" /> : <ListTree size={16} />} Journal de recherche
          </div>
          {dim.etat === "running" && (
            <div style={{ margin: "12px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: "0.8rem", color: "var(--clr-muted)" }}>
                <span>{dim.suivi?.message}</span><span>{fmt(dim.suivi?.progress ?? 0)} %</span>
              </div>
              <div className="progress-bar"><div className="progress-fill" style={{ width: `${dim.suivi?.progress ?? 0}%` }} /></div>
            </div>
          )}
          <pre ref={journalRef} className="journal">{(dim.suivi?.journal ?? []).join("\n")}</pre>
        </div>
      )}

      {dim.erreur && (
        <div className="card" style={{ display: "flex", gap: 12, color: "var(--clr-danger)", marginBottom: "var(--sp-lg)" }}>
          <AlertTriangle size={20} style={{ flexShrink: 0 }} /> <p>{dim.erreur}</p>
        </div>
      )}

      {dim.resultat?.mode === "comparer" && (
        <Comparaison variantes={dim.resultat.variantes} ac={ac} choix={choix} onChoix={setChoix} />
      )}

      {dim.resultat && solution && (
        <Solution key={`${dim.suivi?.task_id}-${choix}`} r={solution} ac={ac} projectId={projectId}
          titre={dim.resultat.mode === "comparer" ? `Variante à ${libP(solution.p_unite, ac)} par sous-station` : "Solution proposée (puissance adaptée à chaque sous-station)"} />
      )}
      {dim.resultat?.mode === "dimensionner" && !dim.resultat.resultat.ok && (
        <div className="card" style={{ display: "flex", gap: 12, color: "var(--clr-warn)" }}>
          <AlertTriangle size={20} style={{ flexShrink: 0 }} /> <p>{dim.resultat.resultat.message}</p>
        </div>
      )}
    </div>
  );
}

function Comparaison({ variantes, ac, choix, onChoix }: {
  variantes: DimResultat[]; ac: boolean; choix: number; onChoix: (i: number) => void;
}) {
  return (
    <div className="card" style={{ marginBottom: "var(--sp-lg)" }}>
      <div className="card-title"><GitCompare size={16} style={{ color: C.violet }} /> Comparaison des puissances unitaires</div>
      <div className="table-container">
        <table className="data-table">
          <thead><tr>
            <th>Puissance unitaire</th><th>Résultat</th><th>Sous-stations</th><th>Postes</th>
            <th>Marge min. (N-1)</th><th>Taux de charge max</th><th>Pertes</th><th></th>
          </tr></thead>
          <tbody>
            {variantes.map((v, i) => {
              const margeMin = v.ok ? Math.min(...v.cas.map(c => c.marge)) : null;
              return (
                <tr key={i} style={{ background: i === choix ? "rgba(59,130,246,0.08)" : undefined }}>
                  <td style={{ fontWeight: 600 }}>{libP(v.p_unite, ac)}</td>
                  <td>{v.ok ? <span className="badge badge-ok">Solution trouvée</span> : <span className="badge badge-error">Aucune solution</span>}</td>
                  <td>{v.ok ? v.n : "–"}{v.ok && v.ajouts_capacite > 0 && <span style={{ color: "var(--clr-muted)", fontSize: "0.75rem" }}> (dont {v.ajouts_capacite} pour la capacité)</span>}</td>
                  <td>{v.ok ? v.postes.length : "–"}</td>
                  <td>{margeMin != null ? `${fmt(margeMin * 100, 1)} %` : "–"}</td>
                  <td>{v.ok ? `${fmt(v.taux_max * 100)} %` : "–"}</td>
                  <td>{v.ok ? fmtE(v.pertes_kwh) : "–"}</td>
                  <td>{v.ok && <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: "0.8rem" }} onClick={() => onChoix(i)}>Voir le détail</button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {variantes.some(v => !v.ok) && (
        <div style={{ marginTop: 12, fontSize: "0.8rem", color: "var(--clr-muted)" }}>
          {variantes.filter(v => !v.ok).map((v, i) => <div key={i}>{libP(v.p_unite, ac)} : {v.message}</div>)}
        </div>
      )}
    </div>
  );
}

function Solution({ r, ac, projectId, titre }: { r: DimResultat; ac: boolean; projectId: string; titre: string }) {
  const verif = useTache<SimulationTask, EtudeResultat>({ statut: getSimStatus, resultat: getSimResult });
  const u = ac ? "kVA" : "kW";

  const schema = useMemo<EChartsOption>(() => ({
    legend: { show: false },
    tooltip: { trigger: "item", formatter: (p: unknown) => (p as { data: { info: string } }).data.info },
    grid: { left: 96, right: 32, top: 24, bottom: 40 },
    xAxis: styledAxis({ type: "value", min: r.d0, max: r.d1, name: "PK (km)", nameLocation: "middle", nameGap: 26 }),
    yAxis: styledAxis({ type: "category", data: ["Postes", "Sous-stations"] as string[], axisTick: { show: false } }),
    series: [
      {
        type: "scatter", symbol: "triangle", symbolSize: 18, itemStyle: { color: C.warn },
        label: { show: true, position: "top", color: C.text, fontSize: 11, formatter: (p: unknown) => (p as { data: { lib: string } }).data.lib },
        data: r.sst.map((s, k) => ({
          value: [s.pk, "Sous-stations"], lib: `${s.nom}\n${libP(r.besoins[k]?.choix, ac)}`,
          info: `${s.nom}<br/>PK ${fmt(s.pk, 3)}<br/>${libP(r.besoins[k]?.choix, ac)}`,
        })),
      },
      {
        type: "scatter", symbol: "diamond", symbolSize: 11,
        label: { show: true, position: "bottom", color: C.muted, fontSize: 10, formatter: (p: unknown) => (p as { data: { lib: string } }).data.lib },
        data: r.postes.map(p => ({
          value: [p.pk, "Postes"], lib: p.type,
          itemStyle: { color: p.type === "SP" ? C.danger : p.type === "PS" ? C.accent : C.primary },
          info: `${p.nom}<br/>PK ${fmt(p.pk, 3)}`,
        })),
      },
    ],
  }), [r, ac]);

  const verifier = () => verif.lancer(() => runSimulation({
    project_id: projectId, dt: 5, couplage: true, n1: true,
    alimentation: { sst: r.sst, postes: r.postes },
  }));

  const kpis = [
    { label: "Sous-stations", value: String(r.n), sub: r.ajouts_capacite ? `dont ${r.ajouts_capacite} pour la capacité` : "" },
    { label: "Postes", value: String(r.postes.length), sub: Array.from(new Set(r.postes.map(p => p.type))).join(" / ") || "aucun" },
    { label: "Taux de charge max", value: `${fmt(r.taux_max * 100)} %`, sub: "requis / calibre" },
    { label: "Énergie SST", value: fmtE(r.energie_kwh), sub: "situation normale" },
    { label: "Pertes", value: fmtE(r.pertes_kwh), sub: "ligne + SST" },
    { label: "Durée de recherche", value: `${fmt(r.duree, 1)} s`, sub: `${r.essais.length} essai${r.essais.length > 1 ? "s" : ""}` },
  ];

  return (
    <div className="fade-in-up">
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <CheckCircle2 size={20} style={{ color: "var(--clr-accent)" }} />
        <span style={{ fontWeight: 700 }}>{titre}</span>
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        {kpis.map(k => (
          <div key={k.label} className="kpi-card">
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ fontSize: "1.4rem" }}>{k.value}</div>
            <div className="kpi-unit">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
        <div className="card-title"><MapPinned size={16} style={{ color: C.warn }} /> Implantation</div>
        <EChart option={schema} height={200} />
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
        <div className="card-title"><Ruler size={16} style={{ color: C.primary }} /> Puissance des sous-stations</div>
        <div className="table-container">
          <table className="data-table">
            <thead><tr>
              <th>Sous-station</th><th>PK</th><th>Charge horaire N</th><th>Charge N-1 max</th><th>Pointe 1 min</th>
              <th>Requis</th><th>Calibre</th><th>Taux</th>{ac && <th>Déséquilibre HT</th>}
            </tr></thead>
            <tbody>
              {r.besoins.map(b => (
                <tr key={b.nom}>
                  <td>{b.nom}</td>
                  <td>{fmt(b.pk, 3)}</td>
                  <td>{fmt(b.charge_n)} {u}</td>
                  <td>{fmt(b.charge_n1)} {u}{b.cas_n1 && <div style={{ color: "var(--clr-muted)", fontSize: "0.75rem" }}>{b.cas_n1}</div>}</td>
                  <td>{fmt(b.pointe)} {u}</td>
                  <td>{fmt(b.requis)} {u}</td>
                  <td style={{ fontWeight: 600 }}>{libP(b.choix, ac)}</td>
                  <td>{b.taux != null ? `${fmt(b.taux * 100)} %` : "–"}</td>
                  {ac && <td>{b.desequilibre_pct != null ? `${fmt(b.desequilibre_pct, 2)} %` : "–"}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
        <div className="card-title"><ShieldCheck size={16} style={{ color: C.violet }} /> Marges par situation (calcul de recherche, marches découplées)</div>
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th>Situation</th><th>Tension minimale</th><th>Tension moy. utile zone min</th><th>Marge de tension</th></tr></thead>
            <tbody>
              {r.cas.map(c => (
                <tr key={c.nom}>
                  <td>{c.nom}</td>
                  <td>{fmtU(c.u_min, ac)}</td>
                  <td>{fmtU(c.u_moy, ac)}</td>
                  <td><span className={`badge ${c.marge >= 0 ? "badge-ok" : "badge-error"}`}>{fmt(c.marge * 100, 1)} %</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
        <div className="card-title"><ShieldCheck size={16} style={{ color: C.accent }} /> Vérification détaillée</div>
        <p style={{ fontSize: "0.85rem", color: "var(--clr-muted)", marginBottom: 12 }}>
          Étude complète de cette solution (effort des engins fonction de la tension réelle, situations N-1),
          sans modifier le projet.
        </p>
        <button className="btn btn-primary" onClick={verifier} disabled={verif.etat === "running"}>
          {verif.etat === "running" ? <><Loader2 size={16} className="spin" /> {verif.suivi?.message} {fmt(verif.suivi?.progress ?? 0)} %</> : <><ShieldCheck size={16} /> Vérifier cette solution</>}
        </button>
        {verif.erreur && <p style={{ color: "var(--clr-danger)", marginTop: 12 }}>{verif.erreur}</p>}
      </div>
      {verif.etat === "done" && verif.resultat && <ResultatsEtude r={verif.resultat} />}
    </div>
  );
}
