/** 管理端专用 DTO：与用户端各写各的，避免跨工程共享类型带来的构建耦合 */

export interface AdminUser {
  id: number;
  username: string;
  is_guest: boolean;
  role: "user" | "admin";
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AdminUser;
}

export interface AuditLogOut {
  id: number;
  actor_id: number | null;
  actor_name: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: string | null;
  affected_rows: number;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditLogPage {
  total: number;
  items: AuditLogOut[];
}
