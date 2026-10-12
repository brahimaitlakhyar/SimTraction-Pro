import { useState, useEffect } from "react";
import { Train, Zap, Gauge } from "lucide-react";
import { getMaterials } from "../api/client";
import type { Material } from "../types";

const SAMPLE: Material[] = [
  { id: "Z21000",   name: "Z 21000 (MI 09)",        type: "EMU",        v_max_kmh: 140, p_max_kw: 5200, system: "AC25kV" },
  { id: "Z2M",      name: "Z 2M",                   type: "DMU",        v_max_kmh: 160, p_max_kw: 1860, system: "diesel" },
  { id: "E1400",    name: "E1400 (Prima II)",        type: "Locomotive", v_max_kmh: 220, p_max_kw: 5500, system: "AC25kV" },
  { id: "Al_Boraq", name: "Al Boraq (TGV M)",        type: "TGV",        v_max_kmh: 320, p_max_kw: 9280, system: "AC25kV" },
  { id: "IORE",     name: "IORE (Alstom cargo)",     type: "Locomotive", v_max_kmh: 100, p_max_kw: 10800, system: "DC3000" },
];

const TYPE_COLORS: Record<string, string> = {
  EMU: "#3b82f6", DMU: "#f59e0b", Locomotive: "#8b5cf6", TGV: "#ef4444",
};

export default function Materials() {
  const [materials, setMaterials] = useState<Material[]>(SAMPLE);

  useEffect(() => {
    getMaterials()
      .then(data => setMaterials(data))
      .catch(() => setMaterials(SAMPLE));
  }, []);

  return (
    <div className="fade-in-up">
      <div className="page-header">
        <h1>Matériel roulant</h1>
        <p>Bibliothèque de référence des rames et locomotives</p>
      </div>

      <div className="table-container card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Matériel</th>
              <th>Type</th>
              <th>V max</th>
              <th>P max</th>
              <th>Système</th>
            </tr>
          </thead>
          <tbody>
            {materials.map(m => (
              <tr key={m.id}>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Train size={16} style={{ color: TYPE_COLORS[m.type] ?? "#64748b" }} />
                    {m.name}
                  </div>
                </td>
                <td>
                  <span className="badge badge-info" style={{ background: `${TYPE_COLORS[m.type]}20`, color: TYPE_COLORS[m.type], borderColor: `${TYPE_COLORS[m.type]}40` }}>
                    {m.type}
                  </span>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <Gauge size={14} style={{ color: "var(--clr-muted)" }} />
                    {m.v_max_kmh} km/h
                  </div>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <Zap size={14} style={{ color: "var(--clr-warn)" }} />
                    {m.p_max_kw.toLocaleString()} kW
                  </div>
                </td>
                <td>
                  <span className="badge badge-info">{m.system}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
