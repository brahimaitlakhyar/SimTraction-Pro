import axios from "axios";
import type { EtudeResultat, Material, Project, SimulationRequest, SimulationTask } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Projects
export const getProjects = () => api.get<Project[]>("/api/v1/projects/").then(r => r.data);
export const getProject  = (id: string) => api.get(`/api/v1/projects/${encodeURIComponent(id)}`).then(r => r.data);

// Simulation
export const runSimulation = (req: SimulationRequest) => api.post<SimulationTask>("/api/v1/simulation/run", req).then(r => r.data);
export const getSimStatus  = (taskId: string) => api.get<SimulationTask>(`/api/v1/simulation/status/${taskId}`).then(r => r.data);
export const getSimResult  = (taskId: string) => api.get<EtudeResultat>(`/api/v1/simulation/result/${taskId}`).then(r => r.data);

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
