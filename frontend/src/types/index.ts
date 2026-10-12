// ──────────────────────────────────────────────────────
// SimTraction Pro – TypeScript type definitions
// (miroir des réponses de l'API / du moteur de calcul)
// ──────────────────────────────────────────────────────

export type SystemType = "cc3000" | "ac1x25" | "ac2x25";

export const SYSTEM_LABELS: Record<SystemType, string> = {
  cc3000: "DC 3 kV",
  ac1x25: "AC 25 kV 1×25",
  ac2x25: "AC 25 kV 2×25",
};

export interface Project {
  id: string;
  nom: string;
  systeme: SystemType;
  reference: string;
  description: string;
  modifie: string;
  longueur_km: number;
  duree_s: number;
  nb_trains: number;
  nb_circulations: number;
  nb_sst: number;
  nb_postes: number;
  version: number;
  dernier_u_min: number | null;
  dernier_conforme: boolean | null;
}

/** Projet complet (format V1 / moteur) ; `_meta.version` sert de verrou optimiste. */
export interface ProjetComplet {
  id: string;
  nom: string;
  systeme: SystemType;
  alimentation: { sst: Record<string, unknown>[]; postes: Record<string, unknown>[]; [k: string]: unknown };
  _meta: { version: number; created_at: string | null; updated_at: string | null };
  [k: string]: unknown;
}

export type SectionProjet = "informations" | "parametres" | "trace" | "materiel" | "trafic" | "sous_stations" | "postes" | "sites";

export interface SimulationRequest {
  project_id: string;
  dt: number;
  couplage: boolean;
  n1: boolean | "interm";
  /** Alimentation proposée à vérifier sans l'enregistrer (solution de dimensionnement). */
  alimentation?: { sst: SstProposee[]; postes: PostePropose[] };
}

export interface SimulationTask {
  task_id: string;
  project_id: string;
  status: "queued" | "running" | "done" | "error";
  opts?: Record<string, unknown>;
  progress: number;
  message: string;
  error?: string | null;
}

export interface Conformite {
  critere: string;
  norme: string;
  valeur: number | null;
  seuil: number;
  ok: boolean;
  txt: string;
  indicatif?: boolean;
}

export interface SstStats {
  nom: string;
  pk: number;
  actif: boolean;
  energie_kwh: number;
  p_max: number;
  i_max: number;
  s_max: number;
  p_15min: number;
  p_1h: number;
  s_1h: number;
  u_min: number | null;
  charge: number;
  desequilibre_pct: number | null;
}

export interface TrainStats {
  id: number;
  nom: string;
  train: string;
  sens: number;
  depart_s: number;
  duree_s: number;
  complet: boolean;
  energie_kwh: number;
  recup_kwh: number;
  u_min: number | null;
  pk_u_min: number;
  u_moy_utile: number | null;
}

export interface Zone {
  pk_debut: number;
  pk_fin: number;
  u_moy_utile: number | null;
  u_min: number | null;
  n: number;
}

export interface Glob {
  energie_sst_kwh: number;
  energie_trains_kwh: number;
  recup_kwh: number;
  pertes_ligne_kwh: number;
  pertes_sst_kwh: number;
  rheostat_kwh: number;
  rendement: number | null;
  u_min: number | null;
  pire: TrainStats | null;
  v_rail_max: number;
  u_moy_zone_min: number | null;
  nb_circ: number;
}

export interface CasN1 {
  nom: string;
  k: number;
  u_min: number | null;
  pk_u_min: number | null;
  u_moy_zone_min: number | null;
  charge_max: number;
  charge_max_nom: string;
  conf: Conformite[];
}

export interface EtudeResultat {
  A: {
    glob: Glob;
    sst: SstStats[];
    trains: TrainStats[];
    zones: Zone[];
    normes: Record<string, number | null>;
    famille: "cc3000" | "ac25";
  };
  conf: Conformite[];
  n1: CasN1[];
  series: {
    circ: { nom: string; train: string; t: number[]; pk: number[]; u: number[]; v: number[] }[];
    t_sst: number[];
    sst: { nom: string; p: number[] }[];
  };
  avert: string[];
  opts: { dt: number; couplage: boolean; n1: boolean | "interm" };
  duree: number;
}

export interface Material {
  ref: number | string;
  nom: string;
  type: string;           // "serie_cc" | "tabule"
  masse_t: number;
  v_max: number;
  p_max_kw: number;
  u_nom: number;
}

export interface KpiCard {
  label: string;
  value: string | number;
  unit: string;
  variant?: "default" | "green" | "warn" | "danger";
  icon?: React.ComponentType<{ size?: number }>;
}

// ── Dimensionnement ─────────────────────────────────────────────────

export interface SstProposee {
  nom: string;
  pk: number;
  en_service: string;
  u0: number;
  p_nom_kw?: number;   // 3 kV
  r_int?: number;      // 3 kV
  s_nom_mva?: number;  // 25 kV
  ucc_pct?: number;
  scc_mva?: number;
}

export interface PostePropose {
  nom: string;
  pk: number;
  type: "PS" | "SP" | "SSP" | "ATS";
  at?: string;
}

export interface Besoin {
  nom: string;
  pk: number;
  charge_n: number;
  charge_n1: number;
  cas_n1: string;
  pointe: number;
  requis: number;
  choix: number | null;
  taux: number | null;
  desequilibre_pct: number | null;
}

export interface DimResultat {
  ok: boolean;
  message?: string;
  n: number;
  sst: SstProposee[];
  postes: PostePropose[];
  besoins: Besoin[];
  cas: { nom: string; marge: number; marge_cap: number | null; u_min: number; u_moy: number | null }[];
  essais: { n: number; pks: number[]; marge: number }[];
  duree: number;
  p_unite: number | null;
  d0: number;
  d1: number;
  pertes_kwh: number;
  energie_kwh: number;
  taux_max: number;
  ajouts_capacite: number;
}

export type DimParametres = Record<string, string | number | boolean | null>;

export interface DimDefauts {
  parametres: DimParametres;
  candidats: { nom: string; pk: number; scc_mva: number }[];
  variantes: number[];
  systeme: SystemType;
}

export type DimSortie =
  | { mode: "dimensionner"; D: DimParametres; resultat: DimResultat; famille: string; systeme: SystemType }
  | { mode: "comparer"; D: DimParametres; variantes: (DimResultat & { D: DimParametres })[]; famille: string; systeme: SystemType };

export interface TacheSuivie extends SimulationTask {
  journal: string[];
}
