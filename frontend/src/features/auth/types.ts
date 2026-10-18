export type Role = "admin" | "staff" | "teacher";

export type Me = {
  id: number;
  username: string;
  display_name: string;
  role: Role;
};
