import { http } from "./client";
import type { AuditLogPage } from "@/types";

export async function fetchAuditLogs(limit = 50): Promise<AuditLogPage> {
  const { data } = await http.get<AuditLogPage>("/api/admin/audit-logs", {
    params: { limit },
  });
  return data;
}
