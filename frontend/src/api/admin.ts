import { http } from "./client";
import type {
  AdminUserPage,
  AdminWord,
  AdminWordPage,
  AdminWordbook,
  AuditLogPage,
  ContentStatus,
  WordbookImportResult,
  KbDocument,
  RagConfig,
  RagPreview,
  UserRole,
  UserStatus,
  ValidationIssue,
  WordRelation,
  WordRelationType,
} from "@/types";

/* ===================== 用户管理 ===================== */

export interface UserQuery {
  search?: string;
  role?: UserRole;
  status?: UserStatus;
  limit?: number;
  offset?: number;
}

export async function fetchUsers(query: UserQuery = {}): Promise<AdminUserPage> {
  const { data } = await http.get<AdminUserPage>("/api/admin/users", { params: query });
  return data;
}

export async function createAdminUser(payload: {
  username: string;
  password: string;
  role?: UserRole;
}): Promise<{ id: number; username: string; role: UserRole }> {
  const { data } = await http.post("/api/admin/users", payload);
  return data;
}

/** 启用 / 封禁 / 调整角色。字段均可选，至少给一项 */
export async function updateUser(
  userId: number,
  payload: { role?: UserRole; status?: UserStatus }
): Promise<{ id: number; username: string; role: UserRole; status: UserStatus }> {
  const { data } = await http.patch(`/api/admin/users/${userId}`, payload);
  return data;
}

/** 删除用户及其全部练习数据（外键级联） */
export async function deleteUser(userId: number): Promise<{ affected_rows: number }> {
  const { data } = await http.delete(`/api/admin/users/${userId}`);
  return data;
}

/* ===================== 词书与词条 ===================== */

export async function fetchAdminWordbooks(): Promise<AdminWordbook[]> {
  const { data } = await http.get<AdminWordbook[]>("/api/admin/wordbooks");
  return data;
}

export async function createWordbook(payload: {
  code: string;
  title: string;
  description?: string;
  difficulty?: string;
}): Promise<AdminWordbook> {
  const { data } = await http.post<AdminWordbook>("/api/admin/wordbooks", payload);
  return data;
}

export async function updateWordbook(
  bookId: number,
  payload: {
    title?: string;
    description?: string;
    difficulty?: string;
    status?: ContentStatus;
  }
): Promise<AdminWordbook> {
  const { data } = await http.patch<AdminWordbook>(`/api/admin/wordbooks/${bookId}`, payload);
  return data;
}

export interface WordQuery {
  search?: string;
  status?: ContentStatus;
  limit?: number;
  offset?: number;
}

export async function fetchAdminWords(
  bookId: number,
  query: WordQuery = {}
): Promise<AdminWordPage> {
  const { data } = await http.get<AdminWordPage>(`/api/admin/wordbooks/${bookId}/words`, {
    params: query,
  });
  return data;
}

export type WordPayload = Pick<
  AdminWord,
  "word" | "phonetic" | "translation" | "example_en" | "example_cn"
>;

export async function createWord(bookId: number, payload: WordPayload): Promise<AdminWord> {
  const { data } = await http.post<AdminWord>(
    `/api/admin/wordbooks/${bookId}/words`,
    payload
  );
  return data;
}

export async function updateWord(wordId: number, payload: WordPayload): Promise<AdminWord> {
  const { data } = await http.patch<AdminWord>(`/api/admin/words/${wordId}`, payload);
  return data;
}

export async function setWordStatus(
  wordId: number,
  status: ContentStatus
): Promise<AdminWord> {
  const { data } = await http.put(`/api/admin/words/${wordId}/status`, null, {
    params: { status },
  });
  return data;
}

/** purge 为 true 表示物理删除，仅在零用户引用时允许 */
export async function deleteWord(wordId: number, purge = false): Promise<unknown> {
  const { data } = await http.delete(`/api/admin/words/${wordId}`, { params: { purge } });
  return data;
}

/**
 * 批量导入词书。
 *
 * 后端先校验后入库，任一条不通过整批不写，422 时把 issues 塞在 detail 里。
 * 结构化错误由 extractIssues 从异常里取出，按 field 定位到「第几条哪个词」。
 */
export async function importWordbooks(payload: unknown): Promise<WordbookImportResult> {
  const { data } = await http.post<WordbookImportResult>("/api/admin/wordbooks/import", payload);
  return data;
}

export async function exportWordbook(bookId: number): Promise<Record<string, unknown>> {
  const { data } = await http.get(`/api/admin/wordbooks/${bookId}/export`);
  return data;
}

/** 从 422 响应里取出结构化校验问题；不是校验错误时返回 null */
export function extractIssues(
  error: unknown
): { message: string; issues: ValidationIssue[] } | null {
  const detail = (error as { detail?: unknown })?.detail;
  if (detail && typeof detail === "object" && "issues" in detail) {
    const typed = detail as { message?: string; issues?: ValidationIssue[] };
    return { message: typed.message ?? "导入文件校验未通过", issues: typed.issues ?? [] };
  }
  return null;
}

/* ===================== 词条关系 ===================== */

export async function fetchRelations(wordId: number): Promise<WordRelation[]> {
  const { data } = await http.get<WordRelation[]>(`/api/admin/words/${wordId}/relations`);
  return data;
}

export async function createRelation(
  wordId: number,
  payload: { tail_word: string; relation: WordRelationType; note?: string }
): Promise<WordRelation> {
  const { data } = await http.post<WordRelation>(
    `/api/admin/words/${wordId}/relations`,
    payload
  );
  return data;
}

export async function updateRelation(
  relationId: number,
  payload: { tail_word?: string; relation?: WordRelationType; note?: string }
): Promise<WordRelation> {
  const { data } = await http.patch<WordRelation>(
    `/api/admin/relations/${relationId}`,
    payload
  );
  return data;
}

export async function deleteRelation(relationId: number): Promise<void> {
  await http.delete(`/api/admin/relations/${relationId}`);
}

/* ===================== 知识库 ===================== */

export async function fetchDocuments(): Promise<KbDocument[]> {
  const { data } = await http.get<KbDocument[]>("/api/admin/kb/documents");
  return data;
}

/** 上传一份资料。走 multipart，解析失败后端直接返回 422 */
export async function uploadDocument(file: File): Promise<KbDocument> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await http.post<KbDocument>("/api/admin/kb/documents", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deleteDocument(documentId: number): Promise<void> {
  await http.delete(`/api/admin/kb/documents/${documentId}`);
}

export async function fetchKbFormats(): Promise<{
  extensions: string[];
  max_bytes: number;
}> {
  const { data } = await http.get("/api/admin/kb/formats");
  return data;
}

/* ===================== 审计 ===================== */

export async function fetchAuditLogs(limit = 50, offset = 0): Promise<AuditLogPage> {
  const { data } = await http.get<AuditLogPage>("/api/admin/audit-logs", {
    params: { limit, offset },
  });
  return data;
}

/* ===================== RAG 调试 ===================== */

export async function fetchRagConfig(): Promise<RagConfig> {
  const { data } = await http.get<RagConfig>("/api/admin/rag/config");
  return data;
}

export async function fetchRagHealth(): Promise<{
  embedding: boolean;
  kb_chunks: number;
  word_chunks: number;
}> {
  const { data } = await http.get("/api/admin/rag/health");
  return data;
}

/** 试跑一次检索，返回完整 trace。调阈值全靠它 */
export async function previewRag(
  query: string,
  history: { role: string; content: string }[] = []
): Promise<RagPreview> {
  const { data } = await http.post<RagPreview>("/api/admin/rag/preview", {
    query,
    history,
  });
  return data;
}
