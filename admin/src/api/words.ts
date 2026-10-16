import { http } from "./client";
import type {
  ImportResult,
  WordAdminOut,
  WordPage,
  WordbookAdminOut,
  WordbookUpdatePayload,
  WordbookCreatePayload,
  WordUpsertPayload,
} from "@/types";

export async function fetchWordbooks(): Promise<WordbookAdminOut[]> {
  const { data } = await http.get<WordbookAdminOut[]>("/api/admin/wordbooks");
  return data;
}

export async function createWordbook(payload: WordbookCreatePayload) {
  const { data } = await http.post<WordbookAdminOut>("/api/admin/wordbooks", payload);
  return data;
}

export async function updateWordbook(bookId: number, payload: WordbookUpdatePayload) {
  const { data } = await http.patch<WordbookAdminOut>(
    `/api/admin/wordbooks/${bookId}`,
    payload
  );
  return data;
}

export async function fetchWords(
  bookId: number,
  params: { search?: string; status?: string; limit?: number; offset?: number }
): Promise<WordPage> {
  const { data } = await http.get<WordPage>(`/api/admin/wordbooks/${bookId}/words`, {
    params: Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== "")
    ),
  });
  return data;
}

export async function createWord(bookId: number, payload: WordUpsertPayload) {
  const { data } = await http.post<WordAdminOut>(
    `/api/admin/wordbooks/${bookId}/words`,
    payload
  );
  return data;
}

export async function updateWord(wordId: number, payload: WordUpsertPayload) {
  const { data } = await http.patch<WordAdminOut>(`/api/admin/words/${wordId}`, payload);
  return data;
}

export async function setWordStatus(wordId: number, status: "active" | "archived") {
  const { data } = await http.put<WordAdminOut>(
    `/api/admin/words/${wordId}/status`,
    null,
    { params: { status } }
  );
  return data;
}

/** 默认下架；purge=true 才走物理删除（后端会校验零引用） */
export async function deleteWord(wordId: number, purge = false) {
  const { data } = await http.delete<{ archived?: boolean; purged?: boolean }>(
    `/api/admin/words/${wordId}`,
    { params: { purge } }
  );
  return data;
}

export async function exportWordbook(bookId: number): Promise<Record<string, unknown>> {
  const { data } = await http.get<Record<string, unknown>>(
    `/api/admin/wordbooks/${bookId}/export`
  );
  return data;
}

/** 批量导入：后端可能返回 422 + 逐条 issues，这里原样抛出由页面解析 */
export async function importWordbooks(payload: unknown): Promise<ImportResult> {
  const { data } = await http.post<ImportResult>("/api/admin/wordbooks/import", payload);
  return data;
}
