import { http } from "./client";
import type { BackupFile, ImportResult } from "@/types";

/** 导出当前账号的学习数据（文件不含任何账号标识） */
export async function fetchBackup(): Promise<BackupFile> {
  const { data } = await http.get<BackupFile>("/api/user/export");
  return data;
}

/** 把一份备份合并进当前账号 */
export async function importBackup(payload: BackupFile): Promise<ImportResult> {
  const { data } = await http.post<ImportResult>("/api/user/import", payload);
  return data;
}
