import { http } from "./client";

/** 健康检查：告诉注册页当前是否需要邀请码 */
export async function fetchHealth(): Promise<{ invite_code_required: boolean }> {
  const { data } = await http.get<{ invite_code_required: boolean }>("/api/admin/health");
  return data;
}

export async function registerAdmin(payload: {
  username: string;
  password: string;
  invite_code?: string;
}) {
  const { data } = await http.post<{ access_token: string }>("/api/admin/auth/register", payload);
  return data;
}
