import axios from "axios";

export function getDefaultApiBase(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
}

function readStoredApiBase(): string | undefined {
  const raw = localStorage.getItem("gridiq_api_base");
  const trimmed = raw?.trim();
  return trimmed || undefined;
}

const runtimeBase = readStoredApiBase();
const defaultBase = getDefaultApiBase();

export const api = axios.create({
  baseURL: runtimeBase ?? defaultBase,
  timeout: 15000,
});

/** Persisted override from Settings. Empty string clears the override and restores the default. */
export function setApiBaseUrl(url: string) {
  const trimmed = url.trim();
  if (!trimmed) {
    localStorage.removeItem("gridiq_api_base");
    api.defaults.baseURL = getDefaultApiBase();
    return;
  }
  api.defaults.baseURL = trimmed;
  localStorage.setItem("gridiq_api_base", trimmed);
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("gridiq_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
