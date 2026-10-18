from datetime import datetime

import aiosqlite

from app.core.database import transaction
from app.core.errors import BadRequest, Forbidden
from app.core.validators import digits_only, now_str, today_str, validate_yyyy_mm_dd
from app.features.actor_records import service as actor_records_service
from app.features.attendance import repository
from app.features.teachers import service as teachers_service

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def get_korean_weekday_short() -> str:
    return WEEKDAYS[datetime.now().weekday()]


def lesson_matches_today(lesson_days: str) -> bool:
    """수업 요일 문자열("월,수", "월/수", "월수금", "월요일" 등)에 오늘 요일이 있는지."""
    if not lesson_days:
        return False

    today_short = get_korean_weekday_short()
    normalized = (
        str(lesson_days).strip()
        .replace("요일", "")
        .replace("/", ",")
        .replace("|", ",")
        .replace("·", ",")
        .replace(" ", "")
    )

    tokens = [x for x in normalized.split(",") if x]
    if today_short in tokens:
        return True

    # "월수금"처럼 붙어 있는 경우
    return today_short in normalized


async def _get_lesson_for_user(db: aiosqlite.Connection, user: dict, lesson_id: int) -> dict | None:
    """teacher는 본인 수업만 조회된다."""
    teacher_user_id = user["id"] if user["role"] == "teacher" else None
    return await repository.get_lesson(db, lesson_id, teacher_user_id)


# ---------- 출석부 ----------

async def get_page_data(db: aiosqlite.Connection, user: dict, lesson_id: str, attendance_date: str) -> dict:
    lesson_id = (lesson_id or "").strip()
    attendance_date = (attendance_date or today_str()).strip()
    try:
        attendance_date = validate_yyyy_mm_dd(attendance_date)
    except Exception:
        attendance_date = today_str()

    if user["role"] == "teacher":
        lessons = [
            {
                "id": x["id"],
                "lesson_name": x["lesson_name"],
                "lesson_days": x["lesson_days"],
                "teacher_user_id": x["teacher_user_id"],
                "teacher_name": user["display_name"],
            }
            for x in await teachers_service.get_teacher_lessons(db, user["id"])
        ]
    else:
        lessons = await repository.list_all_lessons(db)

    if not lesson_id and lessons:
        lesson_id = str(lessons[0]["id"])

    selected_lesson = None
    actors = []
    try:
        lesson_id_int = int(lesson_id) if lesson_id else None
    except Exception:
        lesson_id_int = None

    if lesson_id_int:
        selected_lesson = await _get_lesson_for_user(db, user, lesson_id_int)
        if selected_lesson:
            actors = await repository.list_lesson_actors_with_attendance(db, lesson_id_int, attendance_date)

    return {
        "lessons": lessons,
        "selected_lesson": selected_lesson,
        "lesson_id": lesson_id,
        "attendance_date": attendance_date,
        "actors": actors,
    }


async def save_attendance(db: aiosqlite.Connection, user: dict, form: dict) -> tuple[int, str]:
    """
    출석부 폼을 저장한다. form 키: lesson_id, attendance_date,
    배우마다 phone_input_{id}, status_{id}, feedback_{id}.
    - 상태를 고르지 않았는데 입력한 번호가 맞으면 '출석', 아니면 '미체크'
    - 피드백이 있으면 수업일지에도 "[수업명] 피드백"으로 기록한다 (같은 날 같은 내용은 한 번만)
    반환: (lesson_id, attendance_date)
    """
    lesson_id_raw = str(form.get("lesson_id") or "").strip()
    attendance_date = str(form.get("attendance_date") or "").strip()

    if not lesson_id_raw:
        raise BadRequest("수업을 선택해주세요.")

    # 숫자가 아니면 ValueError로 500이 된다 (docs/found-issues.md #7)
    lesson_id = int(lesson_id_raw)
    attendance_date = validate_yyyy_mm_dd(attendance_date)

    if not await _get_lesson_for_user(db, user, lesson_id):
        raise Forbidden("해당 수업 접근 권한이 없습니다.")

    now = now_str()

    async with transaction(db):
        for actor in await repository.list_lesson_actor_phones(db, lesson_id):
            actor_id = actor["id"]
            saved_last4 = digits_only(actor["phone_last4"], 4)
            phone_input = digits_only(form.get(f"phone_input_{actor_id}"), 4)
            status = str(form.get(f"status_{actor_id}") or "").strip()
            feedback = str(form.get(f"feedback_{actor_id}") or "").strip()

            if not status:
                status = "출석" if saved_last4 and phone_input and saved_last4 == phone_input else "미체크"

            await repository.upsert_with_feedback(
                db, lesson_id, actor_id, attendance_date, status, phone_input, feedback, user["id"], now
            )

            if feedback:
                lesson_name = await repository.get_lesson_name(db, lesson_id)
                content = f"[{lesson_name}] {feedback}" if lesson_name else feedback
                await actor_records_service.add_class_log_if_absent(db, actor_id, attendance_date, content, now)

    return lesson_id, attendance_date


# ---------- 키오스크 ----------

async def get_today_candidates(db: aiosqlite.Connection) -> list[dict]:
    """오늘 요일에 수업이 있는 배우. 여러 수업에 걸쳐 있어도 한 번만 넣는다."""
    today_short = get_korean_weekday_short()
    results = []
    seen = set()

    for row in await repository.list_lesson_assignments(db):
        if not lesson_matches_today(row.get("lesson_days", "")):
            continue
        if row["actor_id"] in seen:
            continue
        seen.add(row["actor_id"])
        row["today_short"] = today_short
        results.append(row)

    return results


async def get_kiosk_page_data(db: aiosqlite.Connection) -> dict:
    return {
        "today_str": today_str(),
        "today_short": get_korean_weekday_short(),
        "today_candidates_count": len(await get_today_candidates(db)),
    }


async def kiosk_check(db: aiosqlite.Connection, user: dict, phone_raw: str) -> dict:
    """번호 뒷자리 4개로 오늘 수업 대상자를 찾아 출석 처리한다. 화면에 보낼 JSON을 반환한다."""
    phone_last4 = digits_only(phone_raw, 4)
    if len(phone_last4) != 4:
        return {"ok": False, "message": "4자리를 입력해주세요."}

    matched = [
        row for row in await get_today_candidates(db)
        if digits_only(row.get("phone_last4"), 4) and digits_only(row.get("phone_last4"), 4) == phone_last4
    ]

    if not matched:
        return {"ok": False, "message": "오늘 출석 대상자 중 일치하는 배우가 없습니다."}

    if len(matched) > 1:
        names = ", ".join([x["name"] for x in matched[:3]])
        return {"ok": False, "message": f"번호가 중복됩니다. 관리자 확인 필요 ({names})"}

    actor = matched[0]
    today = today_str()

    if await repository.get_status(db, actor["lesson_id"], actor["actor_id"], today) == "출석":
        return {
            "ok": True,
            "message": f"{actor['name']} 이미 출석 처리되었습니다.",
            "actor_name": actor["name"],
            "status": "already",
        }

    async with transaction(db):
        await repository.upsert_kiosk_check(
            db, actor["lesson_id"], actor["actor_id"], today, phone_last4, user["id"], now_str()
        )

    return {
        "ok": True,
        "message": f"{actor['name']} 출석 완료",
        "actor_name": actor["name"],
        "status": "checked",
    }
