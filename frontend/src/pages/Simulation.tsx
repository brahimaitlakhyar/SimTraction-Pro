import { useState, useEffect, useMemo } from "react";
import type { EChartsOption } from "echarts";
import { Play, Loader2, CheckCircle2, AlertTriangle, Zap, ShieldCheck, Activity } from "lucide-react";
import { getProjects, runSimulation, getSimStatus, getSimResult, messageErreur } from "../api/client";
import { SYSTEM_LABELS, type Conformite, type EtudeResultat, type Project, type SimulationRequest } from "../types";
import EChart from "../components/EChart";
import { CHART_COLORS as C, styledAxis } from "../components/chartTheme";
import { fmt, fmtU } from "../utils/format";

type Etat = "idle" | "running" | "done" | "error";

interface Props {
  projectId?: string;
}

function BadgeConf({ c }: { c: Pick<Conformite, "ok" | "indicatif"> }) {
  if (c.ok) return <span className="badge badge-ok">Conforme</span>;
  if (c.indicatif) return <span className="badge badge-warn">À examiner</span>;
  return <span className="badge badge-error">Non conforme</span>;
}

export default function Simulation({ projectId }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState<SimulationRequest>({ project_id: projectId ?? "", dt: 5, couplage: true, n1: true });
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [etat, setEtat] = useState<Etat>("idle");
  const [erreur, setErreur] = useState<string | null>(null);
  const [result, setResult] = useState<EtudeResultat | null>(null);

  useEffect(() => {
    getProjects()
      .then(ps => {
        setProjects(ps);
        setForm(f => (f.project_id ? f : { ...f, project_id: ps[0]?.id ?? "" }));
      })
      .catch(e => setErreur(messageErreur(e)));
  }, []);

  // Suivi de l'étude en cours
  useEffect(() => {
    if (!taskId || etat !== "running") return;
    let actif = true;
    let timer: ReturnType<typeof setTimeout>;
    const suivre = async () => {
      try {
        const t = await getSimStatus(taskId);
        if (!actif) return;
        setProgress(t.progress);
        setMessage(t.message);
        if (t.status === "done") {
          const r = await getSimResult(taskId);
          if (!actif) return;
          setResult(r);
          setEtat("done");
          return;
        }
        if (t.status === "error") {
          setErreur(t.error ?? "Erreur de calcul");
          setEtat("error");
          return;
        }
      } catch {
        /* erreur réseau passagère : on réessaie */
      }
      timer = setTimeout(suivre, 700);
    };
    suivre();
    return () => { actif = false; clearTimeout(timer); };
  }, [taskId, etat]);

  const handleRun = async () => {
    setEtat("running");
    setProgress(0);
    setMessage("Envoi…");
    setResult(null);
    setErreur(null);
    try {
      const t = await runSimulation(form);
      setTaskId(t.task_id);
    } catch (e) {
      setErreur(messageErreur(e));
      setEtat("error");
    }
  };

  const projet = projects.find(p => p.id === form.project_id);

  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Lancer une simulation</h1>
        <p>Situation normale et situations dégradées N-1, vérification EN 50163 / EN 50388-1</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "340px minmax(0, 1fr)", gap: "var(--sp-xl)", alignItems: "start" }}>
        {/* Configuration */}
        <div className="card" style={{ position: "sticky", top: "var(--sp-xl)" }}>
          <div className="card-title"><Zap size={16} /> Paramètres de simulation</div>
          <hr className="divider" />

          <div className="form-group">
            <label className="form-label">Projet</label>
            <select className="form-input" value={form.project_id}
              onChange={e => setForm(f => ({ ...f, project_id: e.target.value }))}>
              {projects.map(p => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
            {projet && (
              <div style={{ fontSize: "0.75rem", color: "var(--clr-muted)", marginTop: 6 }}>
                {SYSTEM_LABELS[projet.systeme]} · {fmt(projet.longueur_km, 1)} km · {projet.nb_sst} SST · {projet.nb_circulations} circulations
              </div>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Pas de temps</label>
            <select className="form-input" value={form.dt}
              onChange={e => setForm(f => ({ ...f, dt: +e.target.value }))}>
              {[1, 2, 5, 10].map(d => <option key={d} value={d}>{d} s{d === 1 ? " (précis)" : d === 5 ? " (rapide)" : ""}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Situations dégradées N-1</label>
            <select className="form-input" value={String(form.n1)}
              onChange={e => setForm(f => ({ ...f, n1: e.target.value === "interm" ? "interm" : e.target.value === "true" }))}>
              <option value="true">Chaque sous-station hors service</option>
              <option value="interm">Sous-stations intermédiaires seulement</option>
              <option value="false">Pas de calcul N-1</option>
            </select>
          </div>

          <div className="form-group">
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.875rem" }}>
              <input type="checkbox" checked={form.couplage}
                onChange={e => setForm(f => ({ ...f, couplage: e.target.checked }))} />
              Effort des engins fonction de la tension réelle
            </label>
          </div>

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }}
            onClick={handleRun} disabled={etat === "running" || !form.project_id}>
            {etat === "running"
              ? <><Loader2 size={16} className="spin" /> Calcul en cours…</>
              : <><Play size={16} /> Lancer la simulation</>}
          </button>
        </div>

        {/* Résultats */}
        <div style={{ minWidth: 0 }}>
          {etat === "idle" && !erreur && (
            <div className="card" style={{ textAlign: "center", padding: "60px", color: "var(--clr-muted)" }}>
              <Zap size={48} style={{ margin: "0 auto 16px", opacity: 0.3 }} />
              <p>Choisissez un projet et lancez la simulation pour afficher les résultats.</p>
            </div>
          )}

          {etat === "running" && (
            <div className="card">
              <div className="card-title"><Loader2 size={16} className="spin" /> Calcul en cours…</div>
              <div style={{ margin: "24px 0" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: "0.8rem", color: "var(--clr-muted)" }}>
                  <span>{message}</span><span>{fmt(progress)} %</span>
                </div>
                <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
              </div>
            </div>
          )}

          {erreur && (
            <div className="card" style={{ display: "flex", gap: 12, alignItems: "flex-start", color: "var(--clr-danger)" }}>
              <AlertTriangle size={20} style={{ flexShrink: 0 }} /> <p>{erreur}</p>
            </div>
          )}

          {etat === "done" && result && <Resultats r={result} />}
        </div>
      </div>
    </div>
  );
}

function Resultats({ r }: { r: EtudeResultat }) {
  const ac = r.A.famille !== "cc3000";
  const g = r.A.glob;
  const N = r.A.normes;
  const conforme = r.conf.every(c => c.ok || c.indicatif);
  const n1Conforme = r.n1.every(c => c.conf.every(x => x.ok || x.indicatif));
  const uDiv = ac ? 1000 : 1;
  const uUnit = ac ? "kV" : "V";

  const tensionOption = useMemo<EChartsOption>(() => ({
    legend: { type: "scroll", top: 0, textStyle: { color: C.muted, fontSize: 11 } },
    tooltip: { trigger: "item" },
    grid: { left: 56, right: 24, top: 36, bottom: 48 },
    xAxis: styledAxis({ type: "value", name: "PK (km)", nameLocation: "middle", nameGap: 28, scale: true }),
    yAxis: styledAxis({ type: "value", name: uUnit, scale: true }),
    dataZoom: [{ type: "inside" }],
    series: r.series.circ.map((c, i) => ({
      name: c.nom, type: "line", showSymbol: false, lineStyle: { width: 1.2 },
      data: c.pk.map((pk, k) => [pk, +(c.u[k] / uDiv).toFixed(3)]),
      ...(i === 0 ? {
        markLine: {
          symbol: "none", silent: true,
          label: { color: C.muted, fontSize: 10, formatter: "{b}" },
          data: [
            { name: "Umin1", yAxis: (N.umin1 ?? 0) / uDiv, lineStyle: { color: C.warn, type: "dashed" } },
            { name: "Umin2", yAxis: (N.umin2 ?? 0) / uDiv, lineStyle: { color: C.danger, type: "dashed" } },
          ],
        },
      } : {}),
    })),
  }), [r, uDiv, uUnit, N.umin1, N.umin2]);

  const puissanceOption = useMemo<EChartsOption>(() => ({
    legend: { type: "scroll", top: 0, textStyle: { color: C.muted, fontSize: 11 } },
    grid: { left: 56, right: 24, top: 36, bottom: 48 },
    xAxis: styledAxis({
      type: "value", name: "Temps (h)", nameLocation: "middle", nameGap: 28, min: 0,
      axisLabel: { formatter: (v: number) => fmt(v, 1) },
    }),
    yAxis: styledAxis({ type: "value", name: ac ? "MVA" : "MW" }),
    dataZoom: [{ type: "inside" }],
    series: r.series.sst.map(s => ({
      name: s.nom, type: "line", showSymbol: false, lineStyle: { width: 1.2 },
      data: s.p.map((p, k) => [+(r.series.t_sst[k] / 3600).toFixed(4), +(p / 1000).toFixed(3)]),
    })),
  }), [r, ac]);

  const kpis = [
    { label: "Tension minimale", value: fmtU(g.u_min, ac), sub: g.pire ? g.pire.nom : "", variant: conforme ? "green" : "danger" },
    { label: "Tension moy. utile (zone min)", value: fmtU(g.u_moy_zone_min, ac), sub: "EN 50388-1", variant: "default" },
    { label: "Énergie SST", value: `${fmt(g.energie_sst_kwh / 1000, 2)} MWh`, sub: `${g.nb_circ} circulations`, variant: "default" },
    { label: "Énergie récupérée", value: `${fmt(g.recup_kwh / 1000, 2)} MWh`, sub: "freinage", variant: "green" },
    { label: "Pertes", value: `${fmt((g.pertes_ligne_kwh + g.pertes_sst_kwh) / 1000, 2)} MWh`, sub: "ligne + SST", variant: "warn" },
    { label: "Rendement", value: `${fmt(g.rendement != null ? g.rendement * 100 : null, 1)} %`, sub: "trains / SST", variant: "default" },
  ];

  return (
    <div className="fade-in-up">
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24 }}>
        {conforme && n1Conforme
          ? <CheckCircle2 size={20} style={{ color: "var(--clr-accent)" }} />
          : <AlertTriangle size={20} style={{ color: "var(--clr-danger)" }} />}
        <span style={{ fontWeight: 700 }}>
          Calcul terminé en {fmt(r.duree, 1)} s – {conforme ? "situation normale conforme" : "situation normale non conforme"}
          {r.n1.length > 0 && (n1Conforme ? ", N-1 conforme" : ", N-1 non conforme")}
        </span>
      </div>

      {r.avert.length > 0 && (
        <div className="card" style={{ marginBottom: "var(--sp-md)", color: "var(--clr-warn)", fontSize: "0.85rem" }}>
          {r.avert.map(a => <div key={a}>⚠ {a}</div>)}
        </div>
      )}

      <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        {kpis.map(k => (
          <div key={k.label} className={`kpi-card ${k.variant}`}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ fontSize: "1.4rem" }}>{k.value}</div>
            <div className="kpi-unit">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
        <div className="card-title"><ShieldCheck size={16} style={{ color: C.violet }} /> Conformité – situation normale</div>
        <table className="data-table">
          <thead><tr><th>Critère</th><th>Référence</th><th>Valeur / seuil</th><th>Résultat</th></tr></thead>
          <tbody>
            {r.conf.map(c => (
              <tr key={c.critere}>
                <td>{c.critere}</td>
                <td style={{ color: "var(--clr-muted)", fontSize: "0.8rem" }}>{c.norme}</td>
                <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.8rem" }}>{c.txt}</td>
                <td><BadgeConf c={c} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {r.n1.length > 0 && (
        <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
          <div className="card-title"><AlertTriangle size={16} style={{ color: C.warn }} /> Situations dégradées N-1</div>
          <table className="data-table">
            <thead><tr><th>Situation</th><th>Tension min.</th><th>PK</th><th>Tension moy. utile</th><th>Charge horaire max</th><th>Résultat</th></tr></thead>
            <tbody>
              {r.n1.map(c => {
                const ok = c.conf.every(x => x.ok || x.indicatif);
                return (
                  <tr key={c.nom}>
                    <td>{c.nom}</td>
                    <td>{fmtU(c.u_min, ac)}</td>
                    <td>{fmt(c.pk_u_min, 2)}</td>
                    <td>{fmtU(c.u_moy_zone_min, ac)}</td>
                    <td>{fmt(c.charge_max)} {ac ? "kVA" : "kW"} <span style={{ color: "var(--clr-muted)", fontSize: "0.75rem" }}>({c.charge_max_nom})</span></td>
                    <td><BadgeConf c={{ ok }} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
        <div className="card-title"><Zap size={16} style={{ color: C.primary }} /> Tension au pantographe le long de la ligne</div>
        <EChart option={tensionOption} height={320} />
      </div>

      <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
        <div className="card-title"><Activity size={16} style={{ color: C.accent }} /> Puissance appelée par les sous-stations</div>
        <EChart option={puissanceOption} height={280} />
      </div>

      <div className="card">
        <div className="card-title"><Zap size={16} style={{ color: C.warn }} /> Sous-stations</div>
        <table className="data-table">
          <thead><tr><th>Sous-station</th><th>PK</th><th>Énergie</th><th>Pointe</th><th>Charge horaire</th><th>Tension min.</th></tr></thead>
          <tbody>
            {r.A.sst.map(s => (
              <tr key={s.nom} style={{ opacity: s.actif ? 1 : 0.5 }}>
                <td>{s.nom}{!s.actif && " (hors service)"}</td>
                <td>{fmt(s.pk, 3)}</td>
                <td>{fmt(s.energie_kwh)} kWh</td>
                <td>{fmt(ac ? s.s_max : s.p_max)} {ac ? "kVA" : "kW"}</td>
                <td>{fmt(s.charge)} {ac ? "kVA" : "kW"}</td>
                <td>{fmtU(s.u_min, ac)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
