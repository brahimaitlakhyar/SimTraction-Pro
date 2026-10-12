import { useState, useEffect } from "react";
import { FolderOpen, Plus, Zap, Train, MapPin } from "lucide-react";
import { getProjects } from "../api/client";
import type { Project } from "../types";

const SYSTEM_LABELS: Record<string, string> = {
  DC3000: "DC 3 kV",
  AC25kV_1x25: "AC 25 kV 1×25",
  AC25kV_2x25: "AC 25 kV 2×25",
};

const SAMPLE_PROJECTS: Project[] = [
  { id: "ain_sebaa_kenitra", name: "Ain Sébaâ – Kénitra", system: "AC25kV_2x25", status: "ready", length_km: 140, substations: 3 },
  { id: "casa_rabat_tgv",    name: "Casa – Rabat (TGV)",  system: "AC25kV_2x25", status: "done",  length_km: 90,  substations: 2 },
  { id: "marrakech_agadir",  name: "Marrakech – Agadir",  system: "AC25kV_1x25", status: "ready", length_km: 230, substations: 5 },
  { id: "fes_meknes",        name: "Fès – Meknès",         system: "DC3000",      status: "ready", length_km: 60,  substations: 3 },
  { id: "tangier_port",      name: "Port de Tanger – Gare",system: "AC25kV_1x25", status: "done",  length_km: 45,  substations: 1 },
];

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>(SAMPLE_PROJECTS);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getProjects()
      .then(data => setProjects(data))
      .catch(() => setProjects(SAMPLE_PROJECTS))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="fade-in-up">
      <div className="page-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <h1>Projets</h1>
          <p>Gestion des études de lignes ferroviaires</p>
        </div>
        <button className="btn btn-primary">
          <Plus size={16} /> Nouveau projet
        </button>
      </div>

      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "var(--sp-md)" }}>
          {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 180 }} />)}
        </div>
      )}

      {!loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "var(--sp-md)" }}>
          {projects.map(p => (
            <div key={p.id} className="card" style={{ cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--sp-md)" }}>
                <div style={{ display: "flex", gap: "var(--sp-sm)", alignItems: "center" }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: "var(--r-sm)",
                    background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.2)",
                    display: "flex", alignItems: "center", justifyContent: "center"
                  }}>
                    <Train size={20} style={{ color: "var(--clr-primary)" }} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{p.name}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--clr-muted)" }}>
                      {SYSTEM_LABELS[p.system] ?? p.system}
                    </div>
                  </div>
                </div>
                <span className={`badge ${p.status === "done" ? "badge-ok" : "badge-info"}`}>
                  {p.status === "done" ? "Terminé" : "En attente"}
                </span>
              </div>

              <div style={{ display: "flex", gap: "var(--sp-xl)", fontSize: "0.8rem", color: "var(--clr-muted)", marginBottom: "var(--sp-md)" }}>
                {p.length_km && (
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <MapPin size={12} /> {p.length_km} km
                  </div>
                )}
                {p.substations && (
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <Zap size={12} /> {p.substations} SST
                  </div>
                )}
              </div>

              <div style={{ display: "flex", gap: "var(--sp-sm)" }}>
                <button className="btn btn-ghost" style={{ flex: 1, justifyContent: "center", fontSize: "0.8rem", padding: "8px" }}>
                  <FolderOpen size={14} /> Ouvrir
                </button>
                <button className="btn btn-primary" style={{ flex: 1, justifyContent: "center", fontSize: "0.8rem", padding: "8px" }}>
                  Simuler
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
