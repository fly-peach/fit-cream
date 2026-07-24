/**
 * 统一 API 客户端
 *
 * - 自动附加 Authorization Bearer Token
 * - 解析后端 ResponseModel 信封：{ code, message, data }
 * - 401 时自动登出（清除 token）
 */
import { useAuthStore } from "@/stores/auth-store";

// 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域
const API_URL = "/api";

export class ApiError extends Error {
  code: number;
  constructor(code: number, message: string) {
    super(message);
    this.code = code;
  }
}

interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = useAuthStore.getState().token;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    useAuthStore.getState().logout();
    throw new ApiError(401, "登录已过期，请重新登录");
  }

  let json: Envelope<T>;
  try {
    json = await res.json();
  } catch {
    throw new ApiError(res.status, `请求失败 (${res.status})`);
  }

  if (!res.ok || (json.code !== 0 && json.code !== 200)) {
    throw new ApiError(json.code ?? res.status, json.message ?? "请求失败");
  }

  return json.data;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export { API_URL };