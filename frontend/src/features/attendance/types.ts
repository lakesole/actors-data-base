export type AttendanceLesson = {
  id: number;
  lesson_name: string | null;
  lesson_days: string | null;
  teacher_user_id: number;
  teacher_name?: string | null;
};

export type AttendanceActor = {
  id: number;
  name: string;
  gender: string | null;
  birth_year: number | null;
  phone_last4: string | null;
  status: string | null;
  phone_input: string | null;
  feedback: string | null;
};

export type AttendancePage = {
  lessons: AttendanceLesson[];
  selected_lesson: AttendanceLesson | null;
  lesson_id: string;
  attendance_date: string;
  actors: AttendanceActor[];
};

export type AttendanceEntry = {
  actor_id: number;
  phone_input: string;
  status: string;
  feedback: string;
};

export type KioskInfo = {
  today_str: string;
  today_short: string;
  today_candidates_count: number;
};

export type KioskCheckResult = {
  ok: boolean;
  message: string;
  actor_name: string | null;
  status: "checked" | "already" | null;
};

export const STATUS_OPTIONS: [string, string][] = [
  ["", "자동판별"],
  ["출석", "출석"],
  ["지각", "지각"],
  ["결석", "결석"],
  ["보강", "보강"],
  ["미체크", "미체크"],
];
