// ──────────────────────────────────────────────────────
// SimTraction Pro – TypeScript type definitions
// ──────────────────────────────────────────────────────

export type SystemType = "DC1500" | "DC3000" | "AC25kV_1x25" | "AC25kV_2x25";

export interface Project {
  id: string;
  name: string;
  system: SystemType;
  status: "ready" | "running" | "done" | "error";
  length_km?: number;
  substations?: number;
  created_at?: string;
}

export interface SimulationRequest {
  project_id: string;
  system_type: SystemType;
  peak_hour_trains: number;
  headway_min: number;
  apply_n1: boolean;
  regenerative_braking: boolean;
}

export interface SimulationResult {
  v_min_kV: number;
  v_max_kV: number;
  i_max_A: number;
  energy_mwh: number;
  recovered_mwh: number;
  n1_compliant: boolean;
  voltage_compliant: boolean;
  duration_s: number;
  trains_simulated: number;
}

export interface SimulationTask {
  status: "queued" | "running" | "done" | "error";
  progress: number;
  result?: SimulationResult;
  error?: string;
}

export interface Material {
  id: string;
  name: string;
  type: "EMU" | "DMU" | "Locomotive" | "TGV";
  v_max_kmh: number;
  p_max_kw: number;
  system: string;
}

export interface Substation {
  id: string;
  name: string;
  power_mva: number;
  type: string;
  position_km: number;
}

export interface KpiCard {
  label: string;
  value: string | number;
  unit: string;
  variant?: "default" | "green" | "warn" | "danger";
  icon?: React.ComponentType<{ size?: number }>;
}
