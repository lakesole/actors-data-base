import { api } from "../../shared/api/http";
import type { RecordItem } from "./types";

const base = (actorId: number, path: string) => `/api/actors/${actorId}/${path}`;

export const recordsApi = {
  list: (actorId: number, path: string) => api<RecordItem[]>(base(actorId, path), { allowAnonymous: true }),
  get: (actorId: number, path: string, id: number) => api<RecordItem>(`${base(actorId, path)}/${id}`),
  create: (actorId: number, path: string, body: { date: string; content: string }) =>
    api<RecordItem>(base(actorId, path), { method: "POST", body }),
  update: (actorId: number, path: string, id: number, body: { date: string; content: string }) =>
    api<RecordItem>(`${base(actorId, path)}/${id}`, { method: "PATCH", body }),
  remove: (actorId: number, path: string, id: number) => api(`${base(actorId, path)}/${id}`, { method: "DELETE" }),
};
