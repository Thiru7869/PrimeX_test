import { create } from "zustand";
import type { User } from "@/lib/types";
import { setAccessToken } from "@/lib/apiClient";
import {
  loginApi,
  registerApi,
  logoutApi,
  getMeApi,
  restoreSessionApi,
} from "@/services/authApi";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean; // true while we check for an existing session on load
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email, password) => {
    const data = await loginApi(email, password);
    setAccessToken(data.access_token);
    set({ user: data.user, isAuthenticated: true });
  },

  register: async (email, password, displayName) => {
    const data = await registerApi(email, password, displayName);
    setAccessToken(data.access_token);
    set({ user: data.user, isAuthenticated: true });
  },

  logout: async () => {
    try {
      await logoutApi();
    } finally {
      set({ user: null, isAuthenticated: false });
    }
  },

  // On app load: try to restore via the refresh cookie.
  restore: async () => {
    const token = await restoreSessionApi();
    if (token) {
      try {
        const user = await getMeApi();
        set({ user, isAuthenticated: true, isLoading: false });
        return;
      } catch {
        // fall through to logged-out
      }
    }
    set({ user: null, isAuthenticated: false, isLoading: false });
  },
}));