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
  /** 后端的原始 detail：可能是字符串，也可能是结构化对象（如导入的逐条 issues） */
  readonly detail: unknown;

  constructor(message: string, status = 0, detail?: unknown) {
    super(message);
    this.name = "RequestError";
    this.status = status;
    this.detail = detail;
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
  (error: { response?: { status?: number; data?: { detail?: unknown } } }) => {
    const status = error.response?.status ?? 0;
    const raw = error.response?.data?.detail;
    // detail 可能是对象（导入失败时带逐条 issues），消息只取其中可读的部分
    const message =
      typeof raw === "string"
        ? raw
        : raw && typeof raw === "object" && "message" in raw
          ? String((raw as { message: unknown }).message)
          : status === 0
            ? "网络连接失败"
            : "请求失败";
    // 凭证失效一律退回登录页，绝不带着失效令牌继续操作
    if (status === 401 || status === 403) clearToken();
    return Promise.reject(new RequestError(message, status, raw));
  }
);

export function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : "发生未知错误";
}
