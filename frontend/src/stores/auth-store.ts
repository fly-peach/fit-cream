import { create } from "zustand";

export interface AuthUser {
  id: string;
  role: "user" | "admin";
  name?: string | null;
  phone?: string | null;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  /** 登录：同时写入 token 与用户信息（含 role），持久化到 localStorage */
  setAuth: (token: string, user: AuthUser) => void;
  /** 仅设置 token（兼容旧调用；置空时一并清除 user） */
  setToken: (token: string | null) => void;
  logout: () => void;
}

function loadUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem("fitcream_user");
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem("fitcream_token"),
  user: loadUser(),
  isAuthenticated: !!localStorage.getItem("fitcream_token"),
  setAuth: (token, user) => {
    localStorage.setItem("fitcream_token", token);
    localStorage.setItem("fitcream_user", JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },
  setToken: (token) => {
    if (token) {
      localStorage.setItem("fitcream_token", token);
    } else {
      localStorage.removeItem("fitcream_token");
      localStorage.removeItem("fitcream_user");
    }
    set((state) => ({
      token,
      user: token ? state.user : null,
      isAuthenticated: !!token,
    }));
  },
  logout: () => {
    localStorage.removeItem("fitcream_token");
    localStorage.removeItem("fitcream_user");
    set({ token: null, user: null, isAuthenticated: false });
  },
}));
