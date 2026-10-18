import type { Role } from "../auth/types";

export type User = {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
};

export const ROLES: Role[] = ["teacher", "staff", "admin"];
