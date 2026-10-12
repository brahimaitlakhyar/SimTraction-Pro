import { useState, useEffect } from "react";
import { Zap, Train, MapPin, AlertTriangle, Clock } from "lucide-react";
import { getProjects, messageErreur } from "../api/client";
import { SYSTEM_LABELS, type Project } from "../types";
import { fmt } from "../utils/format";

interface Props {
  onSimuler: (projectId: string) => void;
}

export default function Projects({ onSimuler }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    getProjects()
      .then(setProjects)
      .catch(e => setErreur(messageErreur(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Projets</h1>
        <p>Études de lignes ferroviaires de la base SimTraction V1 ({projects.length} projets)</p>
      </div>

      {erreur && (
        <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", color: "var(--clr-danger)" }}>
          <AlertTriangle size={20} /> {erreur}
        </div>
      )}

      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "var(--sp-md)" }}>
          {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 180 }} />)}
        </div>
      )}

      {!loading && !erreur && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "var(--sp-md)" }}>
          {projects.map(p => (
            <div key={p.id} className="card">
              <div style={{ display: "flex", gap: "var(--sp-sm)", alignItems: "center", marginBottom: "var(--sp-md)" }}>
                <div style={{
                  width: 40, height: 40, borderRadius: "var(--r-sm)", flexShrink: 0,
                  background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center"
                }}>
                  <Train size={20} style={{ color: "var(--clr-primary)" }} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{p.nom}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--clr-muted)" }}>
                    {SYSTEM_LABELS[p.systeme] ?? p.systeme}{p.reference && ` · ${p.reference}`}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: "var(--sp-lg)", fontSize: "0.8rem", color: "var(--clr-muted)", marginBottom: "var(--sp-md)", flexWrap: "wrap" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><MapPin size={12} /> {fmt(p.longueur_km, 1)} km</span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Zap size={12} /> {p.nb_sst} SST</span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Train size={12} /> {p.nb_circulations} circulations</span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Clock size={12} /> {fmt(p.duree_s / 3600, 1)} h</span>
              </div>

              <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center", fontSize: "0.8rem", padding: "8px" }}
                onClick={() => onSimuler(p.id)}>
                Simuler
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
