import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import {
  Zap, TrendingUp, Activity,
  CheckCircle, Train, Cpu, BarChart2
} from "lucide-react";

// ── Mock data ─────────────────────────────────────────────────────
const voltageProfile = Array.from({ length: 20 }, (_, i) => ({
  km: i * 7,
  "V nominal": 25,
  "V min (N)": 19 + Math.random() * 3,
  "V min (N-1)": 17 + Math.random() * 2.5,
}));

const currentData = Array.from({ length: 24 }, (_, i) => ({
  h: `${i}h`,
  current: 200 + Math.random() * 800,
  limit: 1200,
}));

const energyData = [
  { name: "Traction", value: 14.7, fill: "#3b82f6" },
  { name: "Récupérée", value: 3.2,  fill: "#10b981" },
  { name: "Pertes",   value: 1.4,  fill: "#f59e0b" },
];

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
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={voltageProfile} margin={{ left: -10, right: 10 }}>
              <defs>
                <linearGradient id="gN" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gN1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="km" tick={{ fill: "#64748b", fontSize: 11 }} unit=" km" />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} domain={[15, 27]} unit=" kV" />
              <Tooltip contentStyle={{ background: "#1a2235", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 8, color: "#f1f5f9" }} />
              <Legend wrapperStyle={{ fontSize: 12, color: "#64748b" }} />
              <Area type="monotone" dataKey="V nominal" stroke="#64748b" fill="transparent" strokeDasharray="4 4" dot={false} />
              <Area type="monotone" dataKey="V min (N)"  stroke="#3b82f6" fill="url(#gN)"  strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="V min (N-1)" stroke="#ef4444" fill="url(#gN1)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Current over time */}
        <div className="card">
          <div className="card-title"><Activity size={16} style={{ color: "var(--clr-accent)" }} /> Courant SST sur 24h</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={currentData} margin={{ left: -10, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="h" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} unit=" A" />
              <Tooltip contentStyle={{ background: "#1a2235", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 8, color: "#f1f5f9" }} />
              <Legend wrapperStyle={{ fontSize: 12, color: "#64748b" }} />
              <Line type="monotone" dataKey="current" stroke="#10b981" strokeWidth={2} dot={false} name="I SST (A)" />
              <Line type="monotone" dataKey="limit"   stroke="#ef4444" strokeWidth={1} strokeDasharray="4 4" dot={false} name="Limite" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Energy balance */}
        <div className="card">
          <div className="card-title"><BarChart2 size={16} style={{ color: "var(--clr-warn)" }} /> Bilan énergétique (MWh)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={energyData} margin={{ left: -10, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} unit=" MWh" />
              <Tooltip contentStyle={{ background: "#1a2235", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 8, color: "#f1f5f9" }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {energyData.map((e, i) => (
                  <rect key={i} fill={e.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
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
