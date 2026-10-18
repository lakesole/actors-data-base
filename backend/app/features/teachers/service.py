import aiosqlite

from app.core.database import transaction
from app.core.errors import BadRequest, NotFound
from app.core.validators import now_str
from app.features.teachers import repository


async def get_teacher_lessons(db: aiosqlite.Connection, teacher_user_id: int) -> list[dict]:
    """선생님의 수업 목록. 각 수업에 배정된 배우(actors, actor_ids, actor_count)를 붙인다."""
    lessons = await repository.list_lessons(db, teacher_user_id)
    for lesson in lessons:
        actors = await repository.list_lesson_actors(db, lesson["id"])
        lesson["actors"] = actors
        lesson["actor_ids"] = [a["id"] for a in actors]
        lesson["actor_count"] = len(actors)
    return lessons


async def get_teacher_management_rows(db: aiosqlite.Connection) -> list[dict]:
    """관리자 화면용 선생님 목록. 수업과, 수업 전체 기준으로 묶은 배정 배우를 붙인다."""
    teachers = await repository.list_teachers_with_profile(db)

    for teacher in teachers:
        lessons = await get_teacher_lessons(db, teacher["id"])
        teacher["lessons"] = lessons

        merged = {}
        for lesson in lessons:
            for actor in lesson["actors"]:
                merged[actor["id"]] = actor
        teacher["assigned_actors"] = list(merged.values())

    return teachers


async def get_active_teachers(db: aiosqlite.Connection) -> list[dict]:
    """배우 등록/수정 화면의 담당 선생님 선택지."""
    return await repository.list_active_teachers(db)


async def ensure_profile(db: aiosqlite.Connection, user_id: int):
    """teacher 계정의 빈 프로필을 만든다. 호출하는 쪽의 트랜잭션 안에서 실행된다."""
    await repository.insert_empty_profile_if_missing(db, user_id, now_str())


async def save_profile(db: aiosqlite.Connection, teacher_user_id: int, lesson_subject: str, lesson_days: str):
    teacher = await repository.get_user_role(db, teacher_user_id)
    if not teacher:
        raise NotFound("선생님 계정을 찾을 수 없습니다.")
    if teacher["role"] != "teacher":
        raise BadRequest("teacher 계정만 관리할 수 있습니다.")

    async with transaction(db):
        await repository.upsert_profile(
            db, teacher_user_id, (lesson_subject or "").strip(), (lesson_days or "").strip(), now_str()
        )


async def add_lesson(db: aiosqlite.Connection, teacher_user_id: int, lesson_name: str, lesson_days: str):
    """수업명이 비어 있으면 아무것도 하지 않는다."""
    lesson_name = (lesson_name or "").strip()
    lesson_days = (lesson_days or "").strip()
    if not lesson_name:
        return

    async with transaction(db):
        await repository.insert_lesson(db, teacher_user_id, lesson_name, lesson_days, now_str())


async def delete_lesson(db: aiosqlite.Connection, lesson_id: int):
    async with transaction(db):
        await repository.delete_lesson_assignments(db, lesson_id)
        await repository.delete_lesson(db, lesson_id)


async def replace_lesson_actors(db: aiosqlite.Connection, lesson_id: int, raw_actor_ids: list):
    """수업의 배정 배우를 통째로 바꾼다. 숫자가 아닌 값은 무시한다."""
    actor_ids = []
    for actor_id in raw_actor_ids:
        try:
            actor_ids.append(int(str(actor_id).strip()))
        except Exception:
            pass

    if not await repository.get_lesson(db, lesson_id):
        raise NotFound("수업을 찾을 수 없습니다.")

    async with transaction(db):
        await repository.delete_lesson_assignments(db, lesson_id)
        now = now_str()
        for actor_id in actor_ids:
            await repository.insert_assignment(db, lesson_id, actor_id, now)
