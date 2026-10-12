import { useState, useEffect, useCallback } from "react";
import { Zap, Train, MapPin, AlertTriangle, Clock, Plus, Copy, Trash2, X, Check } from "lucide-react";
import { createProject, deleteProject, getProjects, messageErreur } from "../api/client";
import { SYSTEM_LABELS, type Project, type SystemType } from "../types";
import { fmt, fmtU } from "../utils/format";

interface Props {
  onSimuler: (projectId: string) => void;
}

type Edition = { mode: "nouveau" } | { mode: "variante"; source: Project } | null;

export default function Projects({ onSimuler }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [edition, setEdition] = useState<Edition>(null);
  const [aSupprimer, setASupprimer] = useState<string | null>(null);

  const recharger = useCallback(() => {
    getProjects()
      .then(ps => { setProjects(ps); setErreur(null); })
      .catch(e => setErreur(messageErreur(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(recharger, [recharger]);

  const supprimer = async (id: string) => {
    try {
      await deleteProject(id);
      setASupprimer(null);
      recharger();
    } catch (e) {
      setErreur(messageErreur(e));
    }
  };

  return (
    <div className="fade-in-up">
      <div className="page-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <h1>Projets</h1>
          <p>Études de lignes ferroviaires ({projects.length} projets)</p>
        </div>
        <button className="btn btn-primary" onClick={() => setEdition({ mode: "nouveau" })}>
          <Plus size={16} /> Nouveau projet
        </button>
      </div>

      {edition && (
        <FormulaireProjet edition={edition} onAnnuler={() => setEdition(null)}
          onCree={() => { setEdition(null); recharger(); }} />
      )}

      {erreur && (
        <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", color: "var(--clr-danger)", marginBottom: "var(--sp-md)" }}>
          <AlertTriangle size={20} /> {erreur}
        </div>
      )}

      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "var(--sp-md)" }}>
          {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 180 }} />)}
        </div>
      )}

      {!loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "var(--sp-md)" }}>
          {projects.map(p => {
            const ac = p.systeme !== "cc3000";
            return (
              <div key={p.id} className="card" style={{ display: "flex", flexDirection: "column" }}>
                <div style={{ display: "flex", gap: "var(--sp-sm)", alignItems: "center", marginBottom: "var(--sp-md)" }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: "var(--r-sm)", flexShrink: 0,
                    background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.2)",
                    display: "flex", alignItems: "center", justifyContent: "center"
                  }}>
                    <Train size={20} style={{ color: "var(--clr-primary)" }} />
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{p.nom}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--clr-muted)" }}>
                      {SYSTEM_LABELS[p.systeme] ?? p.systeme}{p.reference && ` · ${p.reference}`}
                    </div>
                  </div>
                  {p.dernier_conforme != null && (
                    <span className={`badge ${p.dernier_conforme ? "badge-ok" : "badge-error"}`} title="Dernier calcul">
                      {fmtU(p.dernier_u_min, ac)}
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", gap: "var(--sp-lg)", fontSize: "0.8rem", color: "var(--clr-muted)", marginBottom: "var(--sp-md)", flexWrap: "wrap" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}><MapPin size={12} /> {fmt(p.longueur_km, 1)} km</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Zap size={12} /> {p.nb_sst} SST</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Train size={12} /> {p.nb_circulations} circulations</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Clock size={12} /> {fmt(p.duree_s / 3600, 1)} h</span>
                </div>

                <div style={{ marginTop: "auto", display: "flex", gap: "var(--sp-sm)" }}>
                  {aSupprimer === p.id ? (
                    <>
                      <button className="btn btn-danger" style={{ flex: 1, justifyContent: "center", fontSize: "0.8rem", padding: 8 }}
                        onClick={() => supprimer(p.id)}>
                        <Trash2 size={14} /> Confirmer la suppression
                      </button>
                      <button className="btn btn-ghost" style={{ fontSize: "0.8rem", padding: 8 }} onClick={() => setASupprimer(null)}>
                        Annuler
                      </button>
                    </>
                  ) : (
                    <>
                      <button className="btn btn-primary" style={{ flex: 1, justifyContent: "center", fontSize: "0.8rem", padding: 8 }}
                        onClick={() => onSimuler(p.id)}>
                        Simuler
                      </button>
                      <button className="btn btn-ghost" title="Créer une variante" style={{ fontSize: "0.8rem", padding: 8 }}
                        onClick={() => setEdition({ mode: "variante", source: p })}>
                        <Copy size={14} /> Variante
                      </button>
                      <button className="btn btn-ghost" title="Supprimer" aria-label={`Supprimer ${p.nom}`} style={{ padding: 8 }}
                        onClick={() => setASupprimer(p.id)}>
                        <Trash2 size={14} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FormulaireProjet({ edition, onAnnuler, onCree }: {
  edition: NonNullable<Edition>; onAnnuler: () => void; onCree: () => void;
}) {
  const variante = edition.mode === "variante";
  const [nom, setNom] = useState(variante ? `${edition.source.nom} – variante` : "");
  const [systeme, setSysteme] = useState<SystemType>("cc3000");
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const valider = async () => {
    setEnvoi(true);
    setErreur(null);
    try {
      await createProject(variante ? { nom: nom.trim(), copie_de: edition.source.id } : { nom: nom.trim(), systeme });
      onCree();
    } catch (e) {
      setErreur(messageErreur(e));
      setEnvoi(false);
    }
  };

  return (
    <div className="card" style={{ marginBottom: "var(--sp-lg)" }}>
      <div className="card-title">
        {variante ? <><Copy size={16} /> Variante de « {edition.source.nom} »</> : <><Plus size={16} /> Nouveau projet</>}
      </div>
      <p style={{ fontSize: "0.85rem", color: "var(--clr-muted)", margin: "4px 0 16px" }}>
        {variante
          ? "Copie complète du projet (tracé, matériel, trafic, alimentation, paramètres), à modifier ensuite."
          : "Projet vierge : tracé de 30 km entre deux gares et paramètres par défaut des réglages."}
      </p>
      <form onSubmit={e => { e.preventDefault(); if (nom.trim()) valider(); }}
        style={{ display: "grid", gridTemplateColumns: variante ? "1fr auto" : "1fr 220px auto", gap: "var(--sp-md)", alignItems: "end" }}>
        <div className="form-group" style={{ margin: 0 }}>
          <label className="form-label" htmlFor="nom-projet">Nom du projet</label>
          <input id="nom-projet" className="form-input" value={nom} autoFocus maxLength={200} onChange={e => setNom(e.target.value)} />
        </div>
        {!variante && (
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="systeme-projet">Système</label>
            <select id="systeme-projet" className="form-input" value={systeme} onChange={e => setSysteme(e.target.value as SystemType)}>
              {(Object.keys(SYSTEM_LABELS) as SystemType[]).map(s => <option key={s} value={s}>{SYSTEM_LABELS[s]}</option>)}
            </select>
          </div>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          <button type="submit" className="btn btn-primary" disabled={envoi || !nom.trim()}><Check size={16} /> Créer</button>
          <button type="button" className="btn btn-ghost" onClick={onAnnuler}><X size={16} /> Annuler</button>
        </div>
      </form>
      {erreur && <p style={{ color: "var(--clr-danger)", marginTop: 12 }}>{erreur}</p>}
    </div>
  );
}
