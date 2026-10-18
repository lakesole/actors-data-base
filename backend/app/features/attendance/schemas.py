from pydantic import BaseModel


class LessonOut(BaseModel):
    id: int
    lesson_name: str | None
    lesson_days: str | None
    teacher_user_id: int
    teacher_name: str | None = None


class AttendanceActorOut(BaseModel):
    id: int
    name: str
    gender: str | None
    birth_year: int | None
    phone_last4: str | None
    status: str | None          # 저장된 출결 상태. 아직 저장 전이면 None
    phone_input: str | None
    feedback: str | None


class AttendancePageOut(BaseModel):
    lessons: list[LessonOut]
    selected_lesson: LessonOut | None
    lesson_id: str
    attendance_date: str
    actors: list[AttendanceActorOut]


class AttendanceEntryIn(BaseModel):
    actor_id: int
    phone_input: str = ""
    status: str = ""            # 비우면 번호로 자동판별
    feedback: str = ""


class AttendanceSaveIn(BaseModel):
    lesson_id: int
    attendance_date: str
    entries: list[AttendanceEntryIn]


class KioskInfoOut(BaseModel):
    today_str: str
    today_short: str
    today_candidates_count: int


class KioskCheckIn(BaseModel):
    phone_last4: str


class KioskCheckOut(BaseModel):
    ok: bool
    message: str
    actor_name: str | None = None
    status: str | None = None   # checked / already
