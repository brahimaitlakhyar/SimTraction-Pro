import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Projects
export const getProjects = () => api.get("/api/v1/projects/").then(r => r.data);
export const getProject  = (id: string) => api.get(`/api/v1/projects/${id}`).then(r => r.data);

// Simulation
export const runSimulation   = (req: object) => api.post("/api/v1/simulation/run", req).then(r => r.data);
export const getSimStatus    = (taskId: string) => api.get(`/api/v1/simulation/status/${taskId}`).then(r => r.data);
export const getSimResult    = (taskId: string) => api.get(`/api/v1/simulation/result/${taskId}`).then(r => r.data);

// Materials
export const getMaterials    = () => api.get("/api/v1/materials/").then(r => r.data);

// Substations
export const getSubstations  = () => api.get("/api/v1/substations/").then(r => r.data);
