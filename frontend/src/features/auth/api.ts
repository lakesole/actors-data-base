import { api } from "../../shared/api/http";
import type { Me } from "./types";

export const authApi = {
  me: () => api<Me>("/api/auth/me", { allowAnonymous: true }),
  login: (username: string, password: string) =>
    api<Me>("/api/auth/login", { method: "POST", body: { username, password }, allowAnonymous: true }),
  logout: () => api("/api/auth/logout", { method: "POST" }),
  changePassword: (body: { current_password: string; new_password: string; new_password_confirm: string }) =>
    api("/api/auth/password", { method: "POST", body }),
};
