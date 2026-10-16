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

/** 词书（管理端视角） */
export interface WordbookAdminOut {
  id: number;
  code: string;
  title: string;
  description: string;
  difficulty: string;
  status: "active" | "archived";
  total_words: number;
  archived_words: number;
  active_users: number;
}

export interface WordbookCreatePayload {
  code: string;
  title: string;
  description?: string;
  difficulty?: string;
}

export interface WordbookUpdatePayload {
  title?: string;
  description?: string;
  difficulty?: string;
  status?: "active" | "archived";
}

/** 词条（管理端视角） */
export interface WordAdminOut {
  id: number;
  word: string;
  phonetic: string;
  translation: string;
  example_en: string;
  example_cn: string;
  sequence: number;
  status: "active" | "archived";
}

export interface WordPage {
  total: number;
  items: WordAdminOut[];
}

export interface WordUpsertPayload {
  word: string;
  phonetic: string;
  translation: string;
  example_en: string;
  example_cn: string;
}

/** 导入校验问题，可定位到第几条哪个词 */
export interface ValidationIssueOut {
  rule: string;
  field: string;
  message: string;
}

export interface ImportResult {
  applied: boolean;
  books_created: number;
  books_updated: number;
  words_created: number;
  words_updated: number;
  words_total: number;
  issues: ValidationIssueOut[];
}

/** 导入失败时后端返回的结构化 detail */
export interface ImportFailureDetail {
  message: string;
  issues: ValidationIssueOut[];
}
