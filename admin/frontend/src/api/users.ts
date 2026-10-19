import { http } from "./client";
import type {
  AdminUserListPage,
  CreateUserPayload,
  UpdateUserPayload,
} from "@/types";

export async function fetchUsers(params: {
  search?: string;
  role?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<AdminUserListPage> {
  const { data } = await http.get<AdminUserListPage>("/api/admin/users", {
    params: Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== "")
    ),
  });
  return data;
}

export async function createUser(payload: CreateUserPayload): Promise<{ id: number }> {
  const { data } = await http.post<{ id: number }>("/api/admin/users", payload);
  return data;
}

export async function updateUser(userId: number, payload: UpdateUserPayload) {
  const { data } = await http.patch<{ id: number; role: string; status: string }>(
    `/api/admin/users/${userId}`,
    payload
  );
  return data;
}

export async function deleteUser(userId: number): Promise<{ affected_rows: number }> {
  const { data } = await http.delete<{ affected_rows: number }>(
    `/api/admin/users/${userId}`
  );
  return data;
}
