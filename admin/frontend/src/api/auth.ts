import { http } from "./client";
import type { AdminUser, LoginResponse } from "@/types";

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await http.post<LoginResponse>("/api/admin/auth/login", {
    username,
    password,
  });
  return data;
}

export async function fetchMe(): Promise<AdminUser> {
  const { data } = await http.get<AdminUser>("/api/admin/auth/me");
  return data;
}
