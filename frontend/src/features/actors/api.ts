import { api } from "../../shared/api/http";
import type { Actor, ActorBrief, ActorFields, ActorFiles, ActorList, Video } from "./types";

function toFormData(fields: ActorFields, files: ActorFiles = {}): FormData {
  const fd = new FormData();
  for (const [key, value] of Object.entries(fields)) fd.append(key, value ?? "");
  if (files.photo) fd.append("photo", files.photo);
  if (files.compcard) fd.append("compcard", files.compcard);
  for (const video of files.acting_videos ?? []) fd.append("acting_videos", video);
  return fd;
}

/** 저장된 배우 정보를 수정 폼 값으로 바꾼다 (빠른 업로드에서 나머지 필드를 그대로 보내기 위해) */
export function fieldsFromActor(a: Actor): ActorFields {
  const s = (v: string | number | null) => (v === null || v === undefined ? "" : String(v));
  return {
    name: a.name,
    manager_name: s(a.manager_name),
    teacher_user_id: s(a.teacher_user_id),
    phone_last4: s(a.phone_last4),
    gender: s(a.gender),
    birth_year: s(a.birth_year),
    height_cm: s(a.height_cm),
    weight_kg: s(a.weight_kg),
    school: s(a.school),
    hobby: s(a.hobby),
    specialty: s(a.specialty),
    contract_date: s(a.contract_date),
    contract_end_date: s(a.contract_end_date),
    bio: s(a.bio),
  };
}

export const actorsApi = {
  list: (query: Record<string, string>) => api<ActorList>("/api/actors", { query, allowAnonymous: true }),
  simple: () => api<ActorBrief[]>("/api/actors/simple"),
  get: (id: number) => api<Actor>(`/api/actors/${id}`, { allowAnonymous: true }),
  videos: (id: number) => api<Video[]>(`/api/actors/${id}/videos`, { allowAnonymous: true }),
  create: (fields: ActorFields, files?: ActorFiles) =>
    api<{ id: number }>("/api/actors", { method: "POST", body: toFormData(fields, files) }),
  update: (id: number, fields: ActorFields, files?: ActorFiles) =>
    api<Actor>(`/api/actors/${id}`, { method: "PATCH", body: toFormData(fields, files) }),
  remove: (id: number) => api(`/api/actors/${id}`, { method: "DELETE" }),
  removeVideo: (id: number, videoId: number) => api(`/api/actors/${id}/videos/${videoId}`, { method: "DELETE" }),
};
