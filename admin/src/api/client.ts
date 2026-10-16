import axios from "axios";
import type { AxiosInstance } from "axios";

const TOKEN_KEY = "ep_admin_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class RequestError extends Error {
  readonly status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "RequestError";
    this.status = status;
  }
}

/** 后端地址可配：管理端独立部署，不与用户端共用同一个域名 */
export const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "",
  timeout: 20000,
  headers: { "Content-Type": "application/json" },
});

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: { response?: { status?: number; data?: { detail?: string } } }) => {
    const status = error.response?.status ?? 0;
    const detail =
      error.response?.data?.detail ?? (status === 0 ? "网络连接失败" : "请求失败");
    // 凭证失效一律退回登录页，绝不带着失效令牌继续操作
    if (status === 401 || status === 403) clearToken();
    return Promise.reject(new RequestError(detail, status));
  }
);

export function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : "发生未知错误";
}
