import axios from "axios";
import { create } from "zustand";
import type { User } from "../types";
import { api } from "../lib/api/client";
import * as apiEndpoints from "../lib/api/endpoints";

type AuthState = {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  hydrate: () => Promise<void>;
  logout: () => void;
};

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: false,

  async login(email, password) {
    set({ isLoading: true });
    try {
      const { token, user } = await apiEndpoints.login(email, password);
      localStorage.setItem("gridiq_token", token);
      localStorage.setItem("gridiq_user", JSON.stringify(user));
      set({ token, user });
    } catch (e) {
      if (axios.isAxiosError(e) && !e.response) {
        throw new Error(
          `Cannot reach the API at ${api.defaults.baseURL}. Start the backend (uvicorn on port 8000), or in Settings enable "Use local mocks" / clear a bad API base URL.`,
        );
      }
      throw e;
    } finally {
      set({ isLoading: false });
    }
  },

  async register(email, password) {
    set({ isLoading: true });
    try {
      const { token, user } = await apiEndpoints.register(email, password);
      localStorage.setItem("gridiq_token", token);
      localStorage.setItem("gridiq_user", JSON.stringify(user));
      set({ token, user });
    } catch (e) {
      if (axios.isAxiosError(e) && !e.response) {
        throw new Error(
          `Cannot reach the API at ${api.defaults.baseURL}. Start the backend (uvicorn on port 8000), or in Settings enable "Use local mocks" / clear a bad API base URL.`,
        );
      }
      if (axios.isAxiosError(e) && e.response?.data) {
        const detail = (e.response.data as { detail?: unknown }).detail;
        if (typeof detail === "string") throw new Error(detail);
        if (Array.isArray(detail)) {
          const msg = detail.map((x: { msg?: string }) => x.msg ?? "").filter(Boolean).join(" ");
          if (msg) throw new Error(msg);
        }
      }
      throw e;
    } finally {
      set({ isLoading: false });
    }
  },

  async hydrate() {
    const token = localStorage.getItem("gridiq_token");
    if (!token) return;
    // Mock sign-in uses a placeholder token that is not a valid JWT for the real API.
    if (!apiEndpoints.mocksEnabled() && token === apiEndpoints.MOCK_AUTH_TOKEN) {
      get().logout();
      return;
    }
    set({ isLoading: true });
    try {
      const user = await apiEndpoints.me();
      set({ token, user });
    } catch {
      get().logout();
    } finally {
      set({ isLoading: false });
    }
  },

  logout() {
    localStorage.removeItem("gridiq_token");
    localStorage.removeItem("gridiq_user");
    apiEndpoints.clearAllThreadMessages();
    set({ token: null, user: null });
  },
}));
