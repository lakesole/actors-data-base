from dataclasses import dataclass

import aiosqlite

from app.features.actor_records import repository


@dataclass(frozen=True)
class RecordType:
    path: str        # URL 경로 조각: /actors/{id}/<path>/...
    table: str
    date_field: str  # 날짜 컬럼이자 폼 필드 이름
    tab: str         # 배우 상세 화면 탭
    template: str    # 추가/수정 폼 템플릿


RECORD_TYPES = {
    t.path: t for t in [
        RecordType("classlogs", "class_logs", "meet_date", "classlog", "classlog_form.html"),
        RecordType("auditions", "auditions", "aud_date", "auditions", "audition_form.html"),
        RecordType("casting-management", "casting_management_logs", "meet_date", "casting_management", "casting_management_form.html"),
        RecordType("casting-meetings", "casting_meetings", "meet_date", "casting_meetings", "casting_meeting_form.html"),
        RecordType("first-meetings", "first_meetings", "meet_date", "first_meeting", "first_meeting_form.html"),
    ]
}


async def list_records(db: aiosqlite.Connection, path: str, actor_id: int) -> list[dict]:
    t = RECORD_TYPES[path]
    return await repository.list_by_actor(db, t.table, t.date_field, actor_id)
