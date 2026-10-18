import { api } from "../../shared/api/http";
import type { Teacher, TeacherChoice } from "./types";

export const teachersApi = {
  list: () => api<Teacher[]>("/api/teachers"),
  choices: () => api<TeacherChoice[]>("/api/teachers/choices"),
  addLesson: (teacherId: number, body: { lesson_name: string; lesson_days: string }) =>
    api<{ id: number }>(`/api/teachers/${teacherId}/lessons`, { method: "POST", body }),
  deleteLesson: (lessonId: number) => api(`/api/teachers/lessons/${lessonId}`, { method: "DELETE" }),
  setLessonActors: (lessonId: number, actorIds: number[]) =>
    api(`/api/teachers/lessons/${lessonId}/actors`, { method: "PUT", body: { actor_ids: actorIds } }),
};
