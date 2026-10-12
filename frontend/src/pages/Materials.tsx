import { useState, useEffect } from "react";
import { Train, Zap, Gauge, AlertTriangle } from "lucide-react";
import { getMaterials, messageErreur } from "../api/client";
import type { Material } from "../types";
import { fmt } from "../utils/format";

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  serie_cc: { label: "Moteur série CC", color: "#f59e0b" },
  tabule:   { label: "Triphasé (tabulé)", color: "#3b82f6" },
};

export default function Materials() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    getMaterials()
      .then(setMaterials)
      .catch(e => setErreur(messageErreur(e)));
  }, []);

  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Matériel roulant</h1>
        <p>Bibliothèque commune des engins (BDD/materiel.csv)</p>
      </div>

      {erreur && (
        <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", color: "var(--clr-danger)" }}>
          <AlertTriangle size={20} /> {erreur}
        </div>
      )}

      {!erreur && (
        <div className="table-container card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Réf.</th>
                <th>Désignation</th>
                <th>Modèle de traction</th>
                <th>Masse</th>
                <th>V max</th>
                <th>P max jante</th>
                <th>U nominale</th>
              </tr>
            </thead>
            <tbody>
              {materials.map(m => {
                const t = TYPE_LABELS[m.type] ?? { label: m.type, color: "#64748b" };
                return (
                  <tr key={m.ref}>
                    <td style={{ color: "var(--clr-muted)" }}>{m.ref}</td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Train size={16} style={{ color: t.color }} />
                        {m.nom}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-info" style={{ background: `${t.color}20`, color: t.color, borderColor: `${t.color}40` }}>
                        {t.label}
                      </span>
                    </td>
                    <td>{fmt(m.masse_t)} t</td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <Gauge size={14} style={{ color: "var(--clr-muted)" }} />
                        {fmt(m.v_max)} km/h
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <Zap size={14} style={{ color: "var(--clr-warn)" }} />
                        {fmt(m.p_max_kw)} kW
                      </div>
                    </td>
                    <td>{m.u_nom >= 10000 ? `${fmt(m.u_nom / 1000)} kV` : `${fmt(m.u_nom)} V`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
