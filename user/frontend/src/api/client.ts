import axios, { AxiosError } from "axios";
import type { AxiosInstance } from "axios";
import type { ApiError } from "@/types";

const TOKEN_KEY = "ep_token";
const GUEST_KEY = "ep_guest_id";

/** 统一错误，保证调用方永远拿到可展示的中文文案 */
export class RequestError extends Error {
  readonly status: number;
  readonly retryable: boolean;

  constructor(message: string, status = 0, retryable = false) {
    super(message);
    this.name = "RequestError";
    this.status = status;
    this.retryable = retryable;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getGuestId(): string | null {
  return localStorage.getItem(GUEST_KEY);
}

export function setGuestId(id: string): void {
  localStorage.setItem(GUEST_KEY, id);
}

export function clearGuestId(): void {
  localStorage.removeItem(GUEST_KEY);
}

export const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "",
  timeout: 20000,
  headers: { "Content-Type": "application/json" },
});

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // 游客身份随请求携带，登录 / 注册时后端据此自动迁移历史数据
  const guest = getGuestId();
  if (guest) {
    config.headers["X-Guest-Id"] = guest;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const status = error.response?.status ?? 0;
    const detail =
      error.response?.data?.detail ??
      (status === 0 ? "网络连接失败，请检查网络后重试" : "请求失败，请稍后重试");

    // 凭证失效：清理本地登录态，交由路由守卫跳转登录页
    if (status === 401) {
      clearToken();
      clearGuestId();
    }

    return Promise.reject(new RequestError(detail, status, status >= 500 || status === 0));
  }
);

/** 将任意抛出的异常规整为可展示文案 */
export function toMessage(error: unknown): string {
  if (error instanceof RequestError) return error.message;
  if (error instanceof Error) return error.message;
  return "发生未知错误，请稍后重试";
}
