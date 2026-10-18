import { api } from "../../shared/api/http";
import type { Role } from "../auth/types";
import type { User } from "./types";

export const usersApi = {
  list: () => api<User[]>("/api/users"),
  create: (body: { username: string; password: string; password_confirm: string; display_name: string; role: Role }) =>
    api<User>("/api/users", { method: "POST", body }),
  update: (id: number, body: { is_active?: boolean; role?: Role }) => api<User>(`/api/users/${id}`, { method: "PATCH", body }),
  resetPassword: (id: number, body: { new_password: string; new_password_confirm: string }) =>
    api(`/api/users/${id}/reset-password`, { method: "POST", body }),
  remove: (id: number) => api(`/api/users/${id}`, { method: "DELETE" }),
};
