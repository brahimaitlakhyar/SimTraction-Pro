import { useState, useEffect, useRef } from "react";
import { Play, Loader2, CheckCircle2, AlertTriangle, Zap } from "lucide-react";
import { runSimulation, getSimStatus } from "../api/client";
import type { SimulationResult, SystemType } from "../types";

const SYSTEMS: { value: SystemType; label: string }[] = [
  { value: "DC3000",      label: "DC 3 000 V" },
  { value: "AC25kV_1x25", label: "AC 25 kV – 1×25 (simple fil)" },
  { value: "AC25kV_2x25", label: "AC 25 kV – 2×25 BT/AT" },
];

export default function Simulation() {
  const [form, setForm] = useState({
    project_id: "ain_sebaa_kenitra",
    system_type: "AC25kV_2x25" as SystemType,
    peak_hour_trains: 8,
    headway_min: 7.5,
    apply_n1: true,
    regenerative_braking: true,
  });

  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll simulation status
  useEffect(() => {
    if (taskId && status === "running") {
      pollRef.current = setInterval(async () => {
        try {
          const task = await getSimStatus(taskId);
          setProgress(task.progress ?? 0);
          if (task.status === "done") {
            setResult(task.result);
            setStatus("done");
            clearInterval(pollRef.current!);
          } else if (task.status === "error") {
            setStatus("error");
            clearInterval(pollRef.current!);
          }
        } catch { /* ignore transient errors */ }
      }, 600);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [taskId, status]);

  const handleRun = async () => {
    setStatus("running");
    setProgress(0);
    setResult(null);
    try {
      const { task_id } = await runSimulation(form);
      setTaskId(task_id);
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Lancer une simulation</h1>
        <p>Configurer les paramètres de simulation et analyser le réseau de traction</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: "var(--sp-xl)", alignItems: "start" }}>
        {/* Configuration panel */}
        <div className="card" style={{ position: "sticky", top: "var(--sp-xl)" }}>
          <div className="card-title"><Zap size={16} /> Paramètres de simulation</div>
          <hr className="divider" />

          <div className="form-group">
            <label className="form-label">Projet</label>
            <select className="form-input" value={form.project_id}
              onChange={e => setForm(f => ({ ...f, project_id: e.target.value }))}>
              <option value="ain_sebaa_kenitra">Ain Sébaâ – Kénitra</option>
              <option value="casa_rabat_tgv">Casa – Rabat TGV</option>
              <option value="marrakech_agadir">Marrakech – Agadir</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Système d&apos;alimentation</label>
            <select className="form-input" value={form.system_type}
              onChange={e => setForm(f => ({ ...f, system_type: e.target.value as SystemType }))}>
              {SYSTEMS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Trains / heure de pointe</label>
            <input type="number" className="form-input" min={1} max={30}
              value={form.peak_hour_trains}
              onChange={e => setForm(f => ({ ...f, peak_hour_trains: +e.target.value }))} />
          </div>

          <div className="form-group">
            <label className="form-label">Intervalle minimal (min)</label>
            <input type="number" className="form-input" min={1} max={60} step={0.5}
              value={form.headway_min}
              onChange={e => setForm(f => ({ ...f, headway_min: +e.target.value }))} />
          </div>

          <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.875rem" }}>
              <input type="checkbox" checked={form.apply_n1}
                onChange={e => setForm(f => ({ ...f, apply_n1: e.target.checked }))} />
              Critère N-1 (secours de SST)
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.875rem" }}>
              <input type="checkbox" checked={form.regenerative_braking}
                onChange={e => setForm(f => ({ ...f, regenerative_braking: e.target.checked }))} />
              Freinage récupératif
            </label>
          </div>

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }}
            onClick={handleRun} disabled={status === "running"}>
            {status === "running"
              ? <><Loader2 size={16} className="spin" /> Simulation en cours…</>
              : <><Play size={16} /> Lancer la simulation</>}
          </button>
        </div>

        {/* Results panel */}
        <div>
          {status === "idle" && (
            <div className="card" style={{ textAlign: "center", padding: "60px", color: "var(--clr-muted)" }}>
              <Zap size={48} style={{ margin: "0 auto 16px", opacity: 0.3 }} />
              <p>Configurez les paramètres et lancez une simulation pour afficher les résultats.</p>
            </div>
          )}

          {status === "running" && (
            <div className="card">
              <div className="card-title"><Loader2 size={16} /> Simulation en cours…</div>
              <div style={{ margin: "24px 0" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: "0.8rem", color: "var(--clr-muted)" }}>
                  <span>Progression</span><span>{progress}%</span>
                </div>
                <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
              </div>
              <p style={{ fontSize: "0.85rem", color: "var(--clr-muted)" }}>Calcul cinématique → résolution réseau → analyse N-1…</p>
            </div>
          )}

          {status === "done" && result && (
            <div className="fade-in-up">
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24 }}>
                <CheckCircle2 size={20} style={{ color: "var(--clr-accent)" }} />
                <span style={{ fontWeight: 700 }}>Simulation terminée en {result.duration_s.toFixed(1)}s</span>
              </div>
              <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
                {[
                  { label: "Tension min",     value: result.v_min_kV.toFixed(1),  unit: "kV",   variant: result.v_min_kV < 19 ? "warn" : "green" },
                  { label: "Tension max",     value: result.v_max_kV.toFixed(1),  unit: "kV",   variant: "default" },
                  { label: "Courant max",     value: result.i_max_A,              unit: "A",    variant: "default" },
                  { label: "Énergie tractée", value: result.energy_mwh.toFixed(1), unit: "MWh", variant: "default" },
                  { label: "Énergie récupérée", value: result.recovered_mwh.toFixed(1), unit: "MWh", variant: "green" },
                  { label: "Critère N-1",     value: result.n1_compliant ? "✓ OK" : "✗ KO", unit: "", variant: result.n1_compliant ? "green" : "danger" },
                ].map(k => (
                  <div key={k.label} className={`kpi-card ${k.variant}`}>
                    <div className="kpi-label">{k.label}</div>
                    <div className="kpi-value" style={{ fontSize: "1.4rem" }}>{k.value}</div>
                    <div className="kpi-unit">{k.unit}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {status === "error" && (
            <div className="card" style={{ textAlign: "center", padding: "60px" }}>
              <AlertTriangle size={48} style={{ margin: "0 auto 16px", color: "var(--clr-danger)" }} />
              <p style={{ color: "var(--clr-danger)" }}>Erreur lors de la simulation. Vérifiez les paramètres et réessayez.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
