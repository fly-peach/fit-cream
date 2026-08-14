/**
 * 统一 API 客户端
 *
 * - 同源请求自动携带 httpOnly Cookie 完成认证（无需手动附加 token）
 * - 解析后端 ResponseModel 信封：{ code, message, data }
 * - 401 时自动登出（清除本地会话状态）
 */
import { useAuthStore } from "@/stores/auth-store";
import { API_URL } from "@/lib/api-url";

// 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域。
// App 封装（Capacitor 本地 WebView）时通过 VITE_API_URL 注入绝对地址（见 api-url.ts）。

export class ApiError extends Error {
  code: number;
  constructor(code: number, message: string) {
    super(message);
    this.code = code;
  }
}

/**
 * 判断信封 code 是否为认证失败（类型守卫，命中后将 code 收窄为 number）。
 *
 * 后端认证异常统一返回 HTTP 200 + 业务码，认证段为 401xx
 * （40100 未授权 / 40101 无效 token / 40102 过期 / 40103 凭证无效），
 * 故不能仅依赖 HTTP 状态码判断，需识别该码段以触发自动登出。
 */
export function isAuthError(code: number | null | undefined): code is number {
  return typeof code === "number" && code >= 40100 && code < 40200;
}

/** 认证失效时统一登出并抛出，避免页面停留在「无效的访问令牌」等错误态 */
function handleAuthExpired(code: number): never {
  useAuthStore.getState().logout("登录已过期，请重新登录");
  throw new ApiError(code, "登录已过期，请重新登录");
}

/**
 * 供绕过统一 request 的直接 fetch 调用使用：解析到信封后检测认证失败并登出。
 * 命中 401xx 时抛出（never），调用方应在 try/catch 中调用。
 */
export function checkAuthEnvelope(
  json: { code?: number } | null | undefined
): void {
  const code = json?.code;
  if (isAuthError(code)) {
    handleAuthExpired(code);
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
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (!isFormData) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401) {
    handleAuthExpired(401);
  }

  let json: Envelope<T>;
  try {
    json = await res.json();
  } catch {
    throw new ApiError(res.status, `请求失败 (${res.status})`);
  }

  // 后端认证失败返回 HTTP 200 + 401xx 业务码，需在此识别并自动登出
  if (isAuthError(json.code)) {
    handleAuthExpired(json.code);
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
  /** 上传文件（FormData，浏览器自动设置 multipart boundary，勿手动设 Content-Type） */
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData }),
};

export interface UserApiKeyOut {
  id: string;
  user_id: string;
  key_prefix: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export interface UserApiKeyCreated {
  key: string;
  key_out: UserApiKeyOut;
}

export const apiKeyApi = {
  get: () => api.get<UserApiKeyOut | null>("/users/me/api-key"),
  create: (name?: string) =>
    api.post<UserApiKeyCreated>("/users/me/api-key", name ? { name } : undefined),
  delete: () => api.delete<null>("/users/me/api-key"),
};

export const exerciseFavApi = {
  toggle: (exerciseId: string) =>
    api.post<{ favorited: boolean }>(`/exercises/${exerciseId}/favorite`),
  listIds: () => api.get<string[]>("/exercises/favorites/ids"),
  list: (page = 1, size = 20) =>
    api.get<{ items: import("@/types/exercise").Exercise[]; total: number }>(
      `/exercises/favorites/list?page=${page}&size=${size}`
    ),
};

export { API_URL };