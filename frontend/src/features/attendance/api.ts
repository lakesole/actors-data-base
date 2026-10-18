import { api } from "../../shared/api/http";
import type { AttendanceEntry, AttendancePage, KioskCheckResult, KioskInfo } from "./types";

export const attendanceApi = {
  get: (lessonId: string, attendanceDate: string) =>
    api<AttendancePage>("/api/attendance", { query: { lesson_id: lessonId, attendance_date: attendanceDate } }),
  save: (body: { lesson_id: number; attendance_date: string; entries: AttendanceEntry[] }) =>
    api("/api/attendance", { method: "PUT", body }),

  /** 호출하면 이 브라우저 세션은 키오스크 모드가 된다 */
  kioskInfo: () => api<KioskInfo>("/api/attendance/kiosk"),
  kioskCheck: (phoneLast4: string) =>
    api<KioskCheckResult>("/api/attendance/kiosk/check", { method: "POST", body: { phone_last4: phoneLast4 } }),
  kioskExit: () => api("/api/attendance/kiosk/exit", { method: "POST" }),
};
