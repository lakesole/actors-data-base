from pydantic import BaseModel


class ActorOut(BaseModel):
    id: int
    name: str
    gender: str | None = None
    birth_year: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    school: str | None = None
    hobby: str | None = None
    specialty: str | None = None
    bio: str | None = None
    manager_name: str | None = None
    teacher_user_id: int | None = None
    phone_last4: str | None = None
    contract_date: str | None = None
    contract_end_date: str | None = None
    photo_path: str | None = None
    photo_thumb_path: str | None = None
    compcard_path: str | None = None
    compcard_preview_path: str | None = None

    # 계산 값
    contract_status: str | None = None          # active / expired
    contract_status_label: str | None = None    # 활동중 / 계약만료
    teacher_user_name: str | None = None        # 상세 조회에서만 채워진다
    ai_score: int | None = None                 # AI 검색일 때만 채워진다
    ai_matched: list[str] = []


class AiParsedOut(BaseModel):
    gender: str
    birth_group: str
    height_group: str
    keywords: list[str]
    raw: str


class LessonBrief(BaseModel):
    id: int
    lesson_name: str | None
    lesson_days: str | None


class ActorListOut(BaseModel):
    items: list[ActorOut]
    total_count: int
    total_pages: int
    page: int
    per_page: int
    ai_parsed: AiParsedOut | None
    teacher_lessons: list[LessonBrief]   # teacher가 볼 때 수업 필터 선택지


class ActorBrief(BaseModel):
    id: int
    name: str


class VideoOut(BaseModel):
    id: int
    actor_id: int
    video_path: str
    original_name: str | None
    created_at: str


class CreatedOut(BaseModel):
    id: int
