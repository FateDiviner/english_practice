/** 管理端专用 DTO：与用户端各写各的，避免跨工程共享类型带来的构建耦合 */

export interface AdminUser {
  id: number;
  username: string;
  is_guest: boolean;
  role: "user" | "admin";
  status: "active" | "banned";
  active_wordbook_id: number | null;
  consecutive_days: number;
  created_at: string;
  last_practiced_at: string | null;
  practice_count: number;
}

/** 后端 AdminUserOut 与登录返回的 user 是同一份结构 */
export type AdminUserOut = AdminUser;

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AdminUser;
}

export interface AdminUserListPage {
  total: number;
  items: AdminUserOut[];
}

export interface CreateUserPayload {
  username: string;
  password: string;
  role: "user" | "admin";
}

export interface UpdateUserPayload {
  role?: "user" | "admin";
  status?: "active" | "banned";
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
