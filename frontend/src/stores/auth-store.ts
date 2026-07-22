import { create } from "zustand";

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  setToken: (token: string | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem("fitcream_token"),
  isAuthenticated: !!localStorage.getItem("fitcream_token"),
  setToken: (token) => {
    if (token) {
      localStorage.setItem("fitcream_token", token);
    } else {
      localStorage.removeItem("fitcream_token");
    }
    set({ token, isAuthenticated: !!token });
  },
  logout: () => {
    localStorage.removeItem("fitcream_token");
    set({ token: null, isAuthenticated: false });
  },
}));