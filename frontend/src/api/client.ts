import axios from "axios";
import type { DimDefauts, DimParametres, DimSortie, EtudeResultat, Material, Project, ProjetComplet, SectionProjet, SimulationRequest, SimulationTask, SystemType, TacheSuivie } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Projects
export const getProjects = () => api.get<Project[]>("/api/v1/projects/").then(r => r.data);
export const getProject  = (id: string) => api.get<ProjetComplet>(`/api/v1/projects/${encodeURIComponent(id)}`).then(r => r.data);
export const createProject = (req: { nom: string; systeme?: SystemType; copie_de?: string }) =>
  api.post<ProjetComplet>("/api/v1/projects/", req).then(r => r.data);
export const deleteProject = (id: string) => api.delete(`/api/v1/projects/${encodeURIComponent(id)}`);
/** Remplace une section du projet ; 409 si `version` n'est plus la version courante. */
export const updateSection = (id: string, section: SectionProjet, donnees: unknown, version: number) =>
  api.put<ProjetComplet>(`/api/v1/projects/${encodeURIComponent(id)}/${section}`, { version, donnees }).then(r => r.data);

// Simulation
export const runSimulation = (req: SimulationRequest) => api.post<SimulationTask>("/api/v1/simulation/run", req).then(r => r.data);
export const getSimStatus  = (taskId: string) => api.get<SimulationTask>(`/api/v1/simulation/status/${taskId}`).then(r => r.data);
export const getSimResult  = (taskId: string) => api.get<EtudeResultat>(`/api/v1/simulation/result/${taskId}`).then(r => r.data);

// Dimensionnement
export const getDimParametres = (id: string) =>
  api.get<DimDefauts>(`/api/v1/dimensioning/parametres/${encodeURIComponent(id)}`).then(r => r.data);
export const runDimensionnement = (req: { project_id: string; mode: "dimensionner" | "comparer"; parametres: DimParametres }) =>
  api.post<TacheSuivie>("/api/v1/dimensioning/run", req).then(r => r.data);
export const getDimStatus = (taskId: string) => api.get<TacheSuivie>(`/api/v1/dimensioning/status/${taskId}`).then(r => r.data);
export const getDimResult = (taskId: string) => api.get<DimSortie>(`/api/v1/dimensioning/result/${taskId}`).then(r => r.data);

// Materials
export const getMaterials = () => api.get<Material[]>("/api/v1/materials/").then(r => r.data);

/** Message d'erreur lisible depuis une erreur axios (champ `detail` de FastAPI). */
export function messageErreur(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (typeof d === "string") return d;
    if (!e.response) return "API injoignable : le backend est-il démarré (port 8000) ?";
    return `Erreur ${e.response.status}`;
  }
  return e instanceof Error ? e.message : String(e);
}
