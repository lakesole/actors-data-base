from dataclasses import dataclass

import aiosqlite

from app.core.database import transaction
from app.core.validators import now_iso, validate_yyyy_mm_dd
from app.features.actor_records import repository
from app.features.actors import service as actors_service


@dataclass(frozen=True)
class RecordType:
    path: str        # 화면 URL 경로 조각: /actors/{id}/<path>/...
    api_path: str    # API URL 경로 조각: /api/actors/{id}/<api_path>/...
    table: str
    date_field: str  # 날짜 컬럼이자 화면 폼 필드 이름
    tab: str         # 배우 상세 화면 탭
    template: str    # 추가/수정 폼 템플릿


RECORD_TYPES = {
    t.path: t for t in [
        RecordType("classlogs", "class-logs", "class_logs", "meet_date", "classlog", "classlog_form.html"),
        RecordType("auditions", "auditions", "auditions", "aud_date", "auditions", "audition_form.html"),
        RecordType("casting-management", "casting-management", "casting_management_logs", "meet_date", "casting_management", "casting_management_form.html"),
        RecordType("casting-meetings", "casting-meetings", "casting_meetings", "meet_date", "casting_meetings", "casting_meeting_form.html"),
        RecordType("first-meetings", "first-meetings", "first_meetings", "meet_date", "first_meeting", "first_meeting_form.html"),
    ]
}


async def list_records(db: aiosqlite.Connection, path: str, actor_id: int) -> list[dict]:
    t = RECORD_TYPES[path]
    return await repository.list_by_actor(db, t.table, t.date_field, actor_id)


async def list_records_for_user(db: aiosqlite.Connection, user: dict | None, path: str, actor_id: int) -> list[dict]:
    """상세 화면의 기록 목록. teacher는 담당 배우의 수업일지만 볼 수 있다."""
    await actors_service.ensure_can_view_tab(db, user, actor_id, RECORD_TYPES[path].tab)
    return await list_records(db, path, actor_id)


async def get_record(db: aiosqlite.Connection, path: str, actor_id: int, item_id: int) -> dict | None:
    return await repository.get(db, RECORD_TYPES[path].table, actor_id, item_id)


async def ensure_can_edit(db: aiosqlite.Connection, user: dict, actor_id: int):
    await actors_service.ensure_can_edit(db, user, actor_id)


async def create_record(db: aiosqlite.Connection, user: dict, path: str, actor_id: int, record_date: str, content: str) -> int:
    t = RECORD_TYPES[path]
    await actors_service.ensure_can_edit(db, user, actor_id)
    record_date = validate_yyyy_mm_dd(record_date)

    async with transaction(db):
        return await repository.insert(db, t.table, t.date_field, actor_id, record_date, content, now_iso())


async def update_record(db: aiosqlite.Connection, user: dict, path: str, actor_id: int, item_id: int, record_date: str, content: str):
    t = RECORD_TYPES[path]
    await actors_service.ensure_can_edit(db, user, actor_id)
    record_date = validate_yyyy_mm_dd(record_date)

    async with transaction(db):
        await repository.update(db, t.table, t.date_field, actor_id, item_id, record_date, content)


async def delete_record(db: aiosqlite.Connection, user: dict, path: str, actor_id: int, item_id: int):
    actors_service.ensure_can_delete_record(user)

    async with transaction(db):
        await repository.delete(db, RECORD_TYPES[path].table, actor_id, item_id)


async def add_class_log_if_absent(db: aiosqlite.Connection, actor_id: int, meet_date: str, content: str, created_at: str):
    """같은 날짜, 같은 내용의 수업일지가 없을 때만 추가한다. 호출하는 쪽의 트랜잭션 안에서 실행된다."""
    if not await repository.class_log_exists(db, actor_id, meet_date, content):
        await repository.insert(db, "class_logs", "meet_date", actor_id, meet_date, content, created_at)
