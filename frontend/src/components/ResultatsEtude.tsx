import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { CheckCircle2, AlertTriangle, Zap, ShieldCheck, Activity } from "lucide-react";
import type { Conformite, EtudeResultat } from "../types";
import EChart from "./EChart";
import { CHART_COLORS as C, styledAxis, ZOOM_INTERIEUR } from "./chartTheme";
import { fmt, fmtE, fmtU } from "../utils/format";

export function BadgeConf({ c }: { c: Pick<Conformite, "ok" | "indicatif"> }) {
  if (c.ok) return <span className="badge badge-ok">Conforme</span>;
  if (c.indicatif) return <span className="badge badge-warn">À examiner</span>;
  return <span className="badge badge-error">Non conforme</span>;
}

/** Résultats d'une étude : KPI, conformité, N-1, tension au pantographe, puissance et tableau des SST. */
export default function ResultatsEtude({ r }: { r: EtudeResultat }) {
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
    dataZoom: [ZOOM_INTERIEUR],
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
    dataZoom: [ZOOM_INTERIEUR],
    series: r.series.sst.map(s => ({
      name: s.nom, type: "line", showSymbol: false, lineStyle: { width: 1.2 },
      data: s.p.map((p, k) => [+(r.series.t_sst[k] / 3600).toFixed(4), +(p / 1000).toFixed(3)]),
    })),
  }), [r, ac]);

  const kpis = [
    { label: "Tension minimale", value: fmtU(g.u_min, ac), sub: g.pire ? g.pire.nom : "", variant: conforme ? "green" : "danger" },
    { label: "Tension moy. utile (zone min)", value: fmtU(g.u_moy_zone_min, ac), sub: "EN 50388-1", variant: "default" },
    { label: "Énergie SST", value: fmtE(g.energie_sst_kwh), sub: `${g.nb_circ} circulations`, variant: "default" },
    { label: "Énergie récupérée", value: fmtE(g.recup_kwh), sub: "freinage", variant: "green" },
    { label: "Pertes", value: fmtE(g.pertes_ligne_kwh + g.pertes_sst_kwh), sub: "ligne + SST", variant: "warn" },
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
        <div className="table-container"><table className="data-table">
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
        </table></div>
      </div>

      {r.n1.length > 0 && (
        <div className="card" style={{ marginBottom: "var(--sp-md)" }}>
          <div className="card-title"><AlertTriangle size={16} style={{ color: C.warn }} /> Situations dégradées N-1</div>
          <div className="table-container"><table className="data-table">
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
          </table></div>
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
        <div className="table-container"><table className="data-table">
          <thead><tr><th>Sous-station</th><th>PK</th><th>Énergie</th><th>Pointe</th><th>Charge horaire</th><th>Tension min.</th></tr></thead>
          <tbody>
            {r.A.sst.map(s => (
              <tr key={s.nom} style={{ opacity: s.actif ? 1 : 0.5 }}>
                <td>{s.nom}{!s.actif && " (hors service)"}</td>
                <td>{fmt(s.pk, 3)}</td>
                <td>{fmtE(s.energie_kwh)}</td>
                <td>{fmt(ac ? s.s_max : s.p_max)} {ac ? "kVA" : "kW"}</td>
                <td>{fmt(s.charge)} {ac ? "kVA" : "kW"}</td>
                <td>{fmtU(s.u_min, ac)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>
    </div>
  );
}
