import math
from dataclasses import dataclass

import aiosqlite
from fastapi import UploadFile

from app.core.database import transaction
from app.core.errors import Forbidden, NotFound
from app.core.files import (
    make_thumbnail_from_url,
    normalize_uploadfiles,
    save_upload,
    try_remove_by_url,
)
from app.core.validators import (
    clean_birth_year,
    clean_date,
    default_contract_end_date,
    digits_only,
    now_iso,
    parse_optional_float,
    parse_optional_int,
    today_str,
)
from app.features.actor_records import service as actor_records_service
from app.features.actors import repository
from app.features.actors.repository import ActorFilters
from app.features.actors.search import apply_ai_search
from app.features.compcards import service as compcards_service
from app.features.teachers import service as teachers_service

# 상세 화면 탭 → (템플릿 변수 이름, 기록 종류)
RECORD_TABS = {
    "classlog": ("class_logs", "classlogs"),
    "auditions": ("auditions", "auditions"),
    "casting_management": ("casting_management_logs", "casting-management"),
    "casting_meetings": ("casting_meetings", "casting-meetings"),
    "first_meeting": ("first_meetings", "first-meetings"),
}


@dataclass
class ActorForm:
    """배우 등록/수정 폼 입력값 (정리 전 원본 문자열)."""
    name: str
    manager_name: str = ""
    gender: str = ""
    birth_year: str = ""
    height_cm: str = ""
    weight_kg: str = ""
    school: str = ""
    hobby: str = ""
    specialty: str = ""
    contract_date: str = ""
    contract_end_date: str = ""
    bio: str = ""
    teacher_user_id: str = ""
    phone_last4: str = ""


def make_filters(q="", m="", gender="", height_group="", birth_group="", sort="", status_filter="") -> ActorFilters:
    return ActorFilters(
        q=(q or "").strip(),
        m=(m or "").strip(),
        gender=(gender or "").strip(),
        height_group=(height_group or "").strip(),
        birth_group=(birth_group or "").strip(),
        sort=(sort or "").strip(),
        status_filter=(status_filter or "").strip(),
    )


# ---------- 권한 ----------

def ensure_can_create(user: dict):
    if user["role"] not in ["admin", "staff"]:
        raise Forbidden("배우 등록 권한이 없습니다.")


async def teacher_can_access_actor(db: aiosqlite.Connection, user: dict | None, actor_id: int) -> bool:
    """admin/staff는 항상 가능. teacher는 직접 담당이거나 본인 수업에 배정된 배우만 가능."""
    if not user:
        return False
    if user["role"] in ["admin", "staff"]:
        return True
    if user["role"] != "teacher":
        return False

    if await repository.is_directly_assigned(db, actor_id, user["id"]):
        return True
    return await repository.is_assigned_by_lesson(db, actor_id, user["id"])


async def ensure_can_edit(db: aiosqlite.Connection, user: dict, actor_id: int):
    """배우와 배우 기록을 수정할 수 있는지 확인한다."""
    if user["role"] in ["admin", "staff"]:
        return
    if user["role"] == "teacher":
        if not await teacher_can_access_actor(db, user, actor_id):
            raise Forbidden("담당 배우만 수정할 수 있습니다.")
        return
    raise Forbidden("수정 권한이 없습니다.")


def ensure_can_delete_record(user: dict):
    """배우 기록과 연기영상 삭제는 admin/staff만 가능하다."""
    if user["role"] not in ["admin", "staff"]:
        raise Forbidden("삭제 권한이 없습니다.")


# ---------- 목록 ----------

def _with_contract_status(actor: dict, today: str) -> dict:
    end_date = (actor.get("contract_end_date") or "").strip()
    if end_date and end_date < today:
        actor["contract_status"] = "expired"
        actor["contract_status_label"] = "계약만료"
    else:
        actor["contract_status"] = "active"
        actor["contract_status_label"] = "활동중"
    return actor


async def search_actors(
    db: aiosqlite.Connection,
    f: ActorFilters,
    ai_query: str = "",
    teacher_user_id: int | None = None,
):
    """조건에 맞는 배우 전체. ai_query가 있으면 AI 점수 순으로 거른다.
    반환: (배우 목록, AI 해석 결과, AI 점수 목록)"""
    actors = await repository.list_actors(db, f, teacher_user_id)

    ai_parsed = None
    ai_scored_results = None
    if ai_query:
        ai_scored_results, ai_parsed = apply_ai_search(actors, ai_query)
        actors = [item[0] for item in ai_scored_results]

    return actors, ai_parsed, ai_scored_results


async def get_index_data(
    db: aiosqlite.Connection,
    user: dict | None,
    f: ActorFilters,
    ai_query: str,
    lesson_id: str,
    page: int,
    per_page: int,
) -> dict:
    teacher_user_id = user["id"] if user and user["role"] == "teacher" else None
    teacher_lessons = []
    ai_parsed = None
    ai_scored_results = None

    if ai_query:
        actors, ai_parsed, ai_scored_results = await search_actors(db, f, ai_query, teacher_user_id)
        total_count = len(actors)
        total_pages = max(1, math.ceil(total_count / per_page))
        page = min(page, total_pages)
        start_idx = (page - 1) * per_page
        actors_page = actors[start_idx:start_idx + per_page]
    else:
        if teacher_user_id is not None:
            teacher_lessons = await teachers_service.get_teacher_lessons(db, teacher_user_id)
            actors_page, total_count = await repository.list_teacher_visible_actors_page(
                db, teacher_user_id, f, lesson_id, page, per_page
            )
        else:
            actors_page, total_count = await repository.list_actors_page(db, f, page, per_page)
        total_pages = max(1, math.ceil(total_count / per_page))

    today = today_str()
    actors_page = [_with_contract_status(dict(actor), today) for actor in actors_page]

    return {
        "actors": actors_page,
        "ai_parsed": ai_parsed,
        "ai_scored_results": ai_scored_results,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "teacher_lessons": teacher_lessons,
    }


async def list_actors_simple(db: aiosqlite.Connection) -> list[dict]:
    """수업 배정 화면 등에서 쓰는 전체 배우 이름 목록."""
    return await repository.list_actors_simple(db)


async def get_teacher_choices(db: aiosqlite.Connection) -> list[dict]:
    """배우 등록/수정 화면의 담당 선생님 선택지."""
    return await teachers_service.get_active_teachers(db)


# ---------- 상세 ----------

async def get_detail_data(db: aiosqlite.Connection, user: dict | None, actor_id: int, tab: str) -> dict | None:
    """배우가 없으면 None. teacher는 담당 배우만 볼 수 있고 탭은 수업일지로 고정된다."""
    if user and user["role"] == "teacher":
        if not await teacher_can_access_actor(db, user, actor_id):
            raise Forbidden("담당 배우만 볼 수 있습니다.")
        tab = "classlog"

    actor = await repository.get_actor_with_teacher(db, actor_id)
    if not actor:
        return None

    data = {
        "actor": _with_contract_status(actor, today_str()),
        "tab": tab,
        "class_logs": [],
        "auditions": [],
        "acting_videos": [],
        "casting_management_logs": [],
        "casting_meetings": [],
        "first_meetings": [],
    }

    current_tab = (tab or "compcard").strip()
    if current_tab in RECORD_TABS:
        key, record_path = RECORD_TABS[current_tab]
        data[key] = await actor_records_service.list_records(db, record_path, actor_id)
    elif current_tab == "video":
        data["acting_videos"] = await repository.list_videos(db, actor_id)

    return data


async def get_actor_or_404(db: aiosqlite.Connection, actor_id: int) -> dict:
    actor = await repository.get_actor(db, actor_id)
    if not actor:
        raise NotFound("배우를 찾을 수 없습니다.")
    return actor


# ---------- 등록 / 수정 / 삭제 ----------

def _clean_form(form: ActorForm) -> dict:
    contract_date = clean_date(form.contract_date)
    contract_end_date = clean_date(form.contract_end_date)
    if contract_date and not contract_end_date:
        contract_end_date = default_contract_end_date(contract_date)

    return {
        "name": (form.name or "").strip(),
        "manager_name": (form.manager_name or "").strip(),
        "gender": (form.gender or "").strip(),
        "school": (form.school or "").strip(),
        "hobby": (form.hobby or "").strip(),
        "specialty": (form.specialty or "").strip(),
        "bio": (form.bio or "").strip(),
        "birth_year": clean_birth_year(form.birth_year),
        "contract_date": contract_date,
        "contract_end_date": contract_end_date,
        "height_cm": parse_optional_float(form.height_cm),
        "weight_kg": parse_optional_float(form.weight_kg),
        "teacher_user_id": parse_optional_int(form.teacher_user_id),
    }


def _has_file(file: UploadFile | None) -> bool:
    return bool(file and file.filename)


def _save_photo(photo: UploadFile) -> tuple[str, str | None]:
    photo_path = save_upload(photo, "photo")
    return photo_path, make_thumbnail_from_url(photo_path, "photo_thumb")


def _save_compcard(compcard: UploadFile) -> tuple[str, str | None]:
    compcard_path = save_upload(compcard, "compcard")
    return compcard_path, compcards_service.make_preview(compcard_path, compcard.filename)


async def _save_videos(db: aiosqlite.Connection, actor_id: int, videos):
    now = now_iso()
    for video in normalize_uploadfiles(videos):
        if _has_file(video):
            video_path = save_upload(video, "acting_video")
            await repository.insert_video(db, actor_id, video_path, video.filename, now)


async def create_actor(
    db: aiosqlite.Connection,
    form: ActorForm,
    photo: UploadFile | None,
    compcard: UploadFile | None,
    videos,
) -> int:
    values = _clean_form(form)
    values["phone_last4"] = digits_only(form.phone_last4, 4)
    values["photo_path"], values["photo_thumb_path"] = _save_photo(photo) if _has_file(photo) else (None, None)
    values["compcard_path"], values["compcard_preview_path"] = (
        _save_compcard(compcard) if _has_file(compcard) else (None, None)
    )

    async with transaction(db):
        actor_id = await repository.insert_actor(db, values)
        await _save_videos(db, actor_id, videos)
    return actor_id


async def update_actor(
    db: aiosqlite.Connection,
    actor_id: int,
    form: ActorForm,
    photo: UploadFile | None,
    compcard: UploadFile | None,
    videos,
):
    actor = await get_actor_or_404(db, actor_id)

    values = _clean_form(form)
    # 번호를 비워서 보내면 기존 번호를 유지한다
    values["phone_last4"] = digits_only(form.phone_last4, 4) or digits_only(actor.get("phone_last4"), 4)

    values["photo_path"] = actor.get("photo_path")
    values["photo_thumb_path"] = actor.get("photo_thumb_path")
    if _has_file(photo):
        try_remove_by_url(actor.get("photo_path"))
        try_remove_by_url(actor.get("photo_thumb_path"))
        values["photo_path"], values["photo_thumb_path"] = _save_photo(photo)

    values["compcard_path"] = actor.get("compcard_path")
    values["compcard_preview_path"] = actor.get("compcard_preview_path")
    if _has_file(compcard):
        try_remove_by_url(actor.get("compcard_path"))
        if actor.get("compcard_preview_path") and actor.get("compcard_preview_path") != actor.get("compcard_path"):
            try_remove_by_url(actor.get("compcard_preview_path"))
        values["compcard_path"], values["compcard_preview_path"] = _save_compcard(compcard)

    async with transaction(db):
        await repository.update_actor(db, actor_id, values)
        await _save_videos(db, actor_id, videos)


async def delete_actor(db: aiosqlite.Connection, user: dict, actor_id: int):
    # 현재는 수정 권한으로 삭제를 허용한다 (docs/found-issues.md #3)
    await ensure_can_edit(db, user, actor_id)

    files = await repository.get_actor_files(db, actor_id)
    video_paths = await repository.list_video_paths(db, actor_id)

    async with transaction(db):
        await repository.delete_actor(db, actor_id)

    if files:
        for url in files.values():
            try_remove_by_url(url)
    for url in video_paths:
        try_remove_by_url(url)


async def delete_video(db: aiosqlite.Connection, user: dict, actor_id: int, video_id: int):
    ensure_can_delete_record(user)

    video_path = await repository.get_video_path(db, actor_id, video_id)
    async with transaction(db):
        await repository.delete_video(db, actor_id, video_id)

    try_remove_by_url(video_path)


# ---------- 시작 시 데이터 정리 ----------

async def normalize_actor_data(db: aiosqlite.Connection):
    """출생연도/계약일 형식을 정리하고, 계약 종료일이 비어 있으면 1년으로 채운다."""
    rows = await repository.list_dates_for_normalize(db)

    async with transaction(db):
        for row in rows:
            contract_date = clean_date(row["contract_date"])
            contract_end_date = clean_date(row["contract_end_date"])
            if contract_date and not contract_end_date:
                contract_end_date = default_contract_end_date(contract_date)

            await repository.update_dates(
                db, row["id"], clean_birth_year(row["birth_year"]), contract_date, contract_end_date
            )
