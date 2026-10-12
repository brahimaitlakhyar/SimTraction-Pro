import { useState, useEffect, useRef } from "react";
import { Play, Loader2, AlertTriangle, Zap } from "lucide-react";
import { getProjects, runSimulation, getSimStatus, getSimResult, messageErreur } from "../api/client";
import { SYSTEM_LABELS, type EtudeResultat, type Project, type SimulationRequest, type SimulationTask } from "../types";
import ResultatsEtude from "../components/ResultatsEtude";
import { useTache } from "../hooks/useTache";
import { fmt } from "../utils/format";

interface Props {
  projectId?: string;
}

export default function Simulation({ projectId }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState<SimulationRequest>({ project_id: projectId ?? "", dt: 5, couplage: true, n1: true });
  const [erreurChargement, setErreurChargement] = useState<string | null>(null);
  const tache = useTache<SimulationTask, EtudeResultat>({ statut: getSimStatus, resultat: getSimResult, memoriser: "simtraction.etude" });
  const { etat, resultat: result } = tache;
  const erreur = erreurChargement ?? tache.erreur;
  const progress = tache.suivi?.progress ?? 0;
  const message = tache.suivi?.message ?? "Envoi…";

  useEffect(() => {
    getProjects()
      .then(ps => {
        setProjects(ps);
        setForm(f => (f.project_id ? f : { ...f, project_id: ps[0]?.id ?? "" }));
      })
      .catch(e => setErreurChargement(messageErreur(e)));
  }, []);

  // Étude reprise après un rechargement : afficher son projet et ses options
  const repris = useRef(false);
  useEffect(() => {
    const t = tache.suivi;
    if (!t || repris.current || projectId) return;
    repris.current = true;
    const o = t.opts as Partial<SimulationRequest>;
    setForm(f => ({ ...f, project_id: t.project_id, dt: o.dt ?? f.dt, couplage: o.couplage ?? f.couplage, n1: o.n1 ?? f.n1 }));
  }, [tache.suivi, projectId]);

  const handleRun = () => {
    repris.current = true;
    tache.lancer(() => runSimulation(form));
  };

  const projet = projects.find(p => p.id === form.project_id);

  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Lancer une simulation</h1>
        <p>Situation normale et situations dégradées N-1, vérification EN 50163 / EN 50388-1</p>
      </div>

      <div className="sim-layout">
        {/* Configuration */}
        <div className="card sim-config">
          <div className="card-title"><Zap size={16} /> Paramètres de simulation</div>
          <hr className="divider" />

          <div className="sim-config-champs">
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

          {etat === "done" && result && <ResultatsEtude r={result} />}
        </div>
      </div>
    </div>
  );
}
