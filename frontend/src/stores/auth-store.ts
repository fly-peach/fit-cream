import { create } from "zustand";
import { API_URL } from "@/lib/api-url";

export interface AuthUser {
  id: string;
  role: "user" | "admin";
  name?: string | null;
  phone?: string | null;
}

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  /** 启动时是否已完成会话探测（GET /auth/me），用于避免路由守卫闪跳 */
  isInitialized: boolean;
  /** 被动登出原因（如 token 过期），用于跳转登录页后提示用户 */
  logoutReason: string | null;
  /** 登录成功：token 已由后端写入 httpOnly Cookie，此处仅保存用户信息 */
  setAuth: (user: AuthUser) => void;
  /** 启动探测：GET /auth/me，返回是否已登录 */
  fetchCurrentUser: () => Promise<boolean>;
  logout: (reason?: string) => void;
  clearLogoutReason: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isInitialized: false,
  logoutReason: null,

  setAuth: (user) =>
    set({ user, isAuthenticated: true, logoutReason: null }),

  fetchCurrentUser: async () => {
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        method: "GET",
        credentials: "include",
      });
      const json = await res.json();
      if (json.code === 0 || json.code === 200) {
        set({
          user: json.data as AuthUser,
          isAuthenticated: true,
          isInitialized: true,
          logoutReason: null,
        });
        return true;
      }
    } catch {
      // 网络异常视为未登录，交由重试或路由守卫处理
    }
    set({ user: null, isAuthenticated: false, isInitialized: true });
    return false;
  },

  logout: (reason) => {
    // 尽力清除服务端会话（httpOnly Cookie 由后端删除），失败不影响本地状态
    fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      credentials: "include",
    }).catch(() => {});
    set({
      user: null,
      isAuthenticated: false,
      // 只接受字符串原因，避免事件对象等被误传进 state 渲染报错
      logoutReason: typeof reason === "string" ? reason : null,
    });
  },

  clearLogoutReason: () => set({ logoutReason: null }),
}));
