from pydantic import BaseModel


class RecordIn(BaseModel):
    date: str       # YYYY-MM-DD
    content: str


class RecordOut(BaseModel):
    """기록 5종 공통 응답. 날짜 컬럼 이름(meet_date / aud_date)과 상관없이 date로 내려준다."""
    id: int
    actor_id: int
    date: str
    content: str
    created_at: str
