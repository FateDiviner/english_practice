import { http } from "./client";
import type { WordBook, WordBookProgress } from "@/types";

/** 拉取全部内置词书 */
export async function fetchWordbooks(): Promise<WordBook[]> {
  const { data } = await http.get<WordBook[]>("/api/wordbooks");
  return data;
}

/** 拉取指定词书的学习进度 */
export async function fetchProgress(wordbookId: number): Promise<WordBookProgress> {
  const { data } = await http.get<WordBookProgress>(`/api/wordbooks/${wordbookId}/progress`);
  return data;
}

/** 激活（切换）当前词书 */
export async function activateWordbook(wordbookId: number): Promise<WordBook> {
  const { data } = await http.post<WordBook>(`/api/wordbooks/${wordbookId}/activate`);
  return data;
}
