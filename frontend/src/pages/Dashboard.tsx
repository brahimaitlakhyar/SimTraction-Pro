import type { EChartsOption } from "echarts";
import {
  Zap, TrendingUp, Activity,
  CheckCircle, Train, Cpu, BarChart2
} from "lucide-react";
import EChart from "../components/EChart";
import { CHART_COLORS as C, styledAxis } from "../components/chartTheme";

// ── Mock data ─────────────────────────────────────────────────────
const voltageProfile = Array.from({ length: 20 }, (_, i) => ({
  km: i * 7,
  vMinN: 19 + Math.random() * 3,
  vMinN1: 17 + Math.random() * 2.5,
}));

const currentData = Array.from({ length: 24 }, (_, i) => ({
  h: `${i}h`,
  current: 200 + Math.random() * 800,
  limit: 1200,
}));

const energyData = [
  { name: "Traction", value: 14.7, fill: C.primary },
  { name: "Récupérée", value: 3.2,  fill: C.accent },
  { name: "Pertes",   value: 1.4,  fill: C.warn },
];

// ── Chart options ─────────────────────────────────────────────────
const areaGradient = (color: string, opacity: number) => ({
  type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1,
  colorStops: [
    { offset: 0, color: color + Math.round(opacity * 255).toString(16).padStart(2, "0") },
    { offset: 1, color: color + "00" },
  ],
});

const voltageOption: EChartsOption = {
  xAxis: styledAxis({ type: "value", min: 0, max: 133, axisLabel: { formatter: "{value} km" } }),
  yAxis: styledAxis({ type: "value", min: 15, max: 27, axisLabel: { formatter: "{value} kV" } }),
  series: [
    { name: "V nominal", type: "line", showSymbol: false, data: voltageProfile.map(d => [d.km, 25]),
      lineStyle: { color: C.muted, type: "dashed", width: 1 }, itemStyle: { color: C.muted } },
    { name: "V min (N)", type: "line", smooth: true, showSymbol: false, data: voltageProfile.map(d => [d.km, +d.vMinN.toFixed(2)]),
      lineStyle: { color: C.primary, width: 2 }, itemStyle: { color: C.primary }, areaStyle: { color: areaGradient(C.primary, 0.3) } },
    { name: "V min (N-1)", type: "line", smooth: true, showSymbol: false, data: voltageProfile.map(d => [d.km, +d.vMinN1.toFixed(2)]),
      lineStyle: { color: C.danger, width: 2 }, itemStyle: { color: C.danger }, areaStyle: { color: areaGradient(C.danger, 0.2) } },
  ],
};

const currentOption: EChartsOption = {
  xAxis: styledAxis({ type: "category", data: currentData.map(d => d.h) }),
  yAxis: styledAxis({ type: "value", axisLabel: { formatter: "{value} A" } }),
  series: [
    { name: "I SST (A)", type: "line", smooth: true, showSymbol: false, data: currentData.map(d => Math.round(d.current)),
      lineStyle: { color: C.accent, width: 2 }, itemStyle: { color: C.accent } },
    { name: "Limite", type: "line", showSymbol: false, data: currentData.map(d => d.limit),
      lineStyle: { color: C.danger, width: 1, type: "dashed" }, itemStyle: { color: C.danger } },
  ],
};

const energyOption: EChartsOption = {
  legend: { show: false },
  xAxis: styledAxis({ type: "category", data: energyData.map(e => e.name) }),
  yAxis: styledAxis({ type: "value", axisLabel: { formatter: "{value} MWh" } }),
  grid: { left: 64, right: 16, top: 16, bottom: 28 },
  series: [{
    type: "bar", barMaxWidth: 64,
    data: energyData.map(e => ({ value: e.value, itemStyle: { color: e.fill, borderRadius: [6, 6, 0, 0] } })),
  }],
};

// ── KPI data ─────────────────────────────────────────────────────
const kpis = [
  { label: "Tension minimale", value: "18.4", unit: "kV",  variant: "warn",    icon: Zap },
  { label: "Courant max SST",  value: "1 240", unit: "A",  variant: "default", icon: Activity },
  { label: "Énergie tractée",  value: "14.7",  unit: "MWh", variant: "default", icon: TrendingUp },
  { label: "Énergie récupérée",value: "3.2",   unit: "MWh", variant: "green",   icon: CheckCircle },
  { label: "Trains simulés",   value: "8",      unit: "trains/h", variant: "default", icon: Train },
  { label: "Critère N-1",      value: "✓",     unit: "Conforme", variant: "green",  icon: CheckCircle },
];

export default function Dashboard() {
  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Tableau de bord</h1>
        <p>Vue d&apos;ensemble de la dernière simulation – Ain Sébaâ → Kénitra (2×25 kV)</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        {kpis.map((k) => {
          const Icon = k.icon;
          return (
            <div key={k.label} className={`kpi-card ${k.variant ?? ""}`}>
              <div className="kpi-icon"><Icon size={48} /></div>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-unit">{k.unit}</div>
            </div>
          );
        })}
      </div>

      {/* Charts */}
      <div className="charts-grid">
        {/* Voltage Profile */}
        <div className="card">
          <div className="card-title"><Zap size={16} style={{ color: "var(--clr-primary)" }} /> Profil de tension en ligne</div>
          <EChart option={voltageOption} />
        </div>

        {/* Current over time */}
        <div className="card">
          <div className="card-title"><Activity size={16} style={{ color: "var(--clr-accent)" }} /> Courant SST sur 24h</div>
          <EChart option={currentOption} />
        </div>

        {/* Energy balance */}
        <div className="card">
          <div className="card-title"><BarChart2 size={16} style={{ color: "var(--clr-warn)" }} /> Bilan énergétique (MWh)</div>
          <EChart option={energyOption} />
        </div>

        {/* Normative summary */}
        <div className="card">
          <div className="card-title"><Cpu size={16} style={{ color: "#8b5cf6" }} /> Vérifications normatives</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Critère</th>
                <th>Valeur</th>
                <th>Limite</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {[
                { c: "Vmin (N) EN 50163",    val: "18.4 kV", lim: "17.5 kV", ok: true },
                { c: "Vmin (N-1) EN 50388",  val: "16.8 kV", lim: "15.0 kV", ok: true },
                { c: "Icc SST EN 60909",     val: "14.2 kA", lim: "25.0 kA", ok: true },
                { c: "Courant crête SST",    val: "1 240 A",  lim: "1 500 A", ok: true },
                { c: "Taux harmonique",      val: "3.2 %",   lim: "5.0 %",   ok: true },
                { c: "Facteur de puissance", val: "0.88",    lim: "0.80",    ok: true },
              ].map(row => (
                <tr key={row.c}>
                  <td style={{ fontSize: "0.8rem" }}>{row.c}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{row.val}</td>
                  <td style={{ color: "var(--clr-muted)", fontSize: "0.8rem" }}>{row.lim}</td>
                  <td><span className={`badge ${row.ok ? "badge-ok" : "badge-error"}`}>{row.ok ? "✓ OK" : "✗ KO"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
