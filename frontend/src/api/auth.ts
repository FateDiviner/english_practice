import { http, setToken, setGuestId, clearGuestId } from "./client";
import type { AuthResponse, UserInfo } from "@/types";

/** 注册；若当前是游客会话，后端会自动把进度迁移到新账号 */
export async function register(username: string, password: string): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>("/api/auth/register", {
    username,
    password,
  });
  setToken(data.access_token);
  clearGuestId();
  return data;
}

/** 登录，同样触发游客数据迁移 */
export async function login(username: string, password: string): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>("/api/auth/login", {
    username,
    password,
  });
  setToken(data.access_token);
  clearGuestId();
  return data;
}

/** 一键游客体验 */
export async function guestLogin(): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>("/api/auth/guest", {});
  setToken(data.access_token);
  setGuestId(String(data.user.id));
  return data;
}

/** 读取当前登录用户 */
export async function fetchMe(): Promise<UserInfo> {
  const { data } = await http.get<UserInfo>("/api/auth/me");
  return data;
}
