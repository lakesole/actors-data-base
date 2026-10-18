import os
import uuid
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from urllib.parse import quote

import aiosqlite
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pptx import Presentation
from pypdf import PdfWriter
from starlette.middleware.sessions import SessionMiddleware

from app.core.auth import (
    require_actor_edit_permission,
    require_admin_legacy as require_admin,
    require_login_user,
    require_record_delete_permission,
)
from app.core.config import (
    DB_PATH,
    MERGED_DIR,
    SECRET_KEY,
    SESSION_COOKIE_NAME,
    SESSION_HTTPS_ONLY,
    SESSION_MAX_AGE,
    STATIC_DIR,
)
from app.core.database import open_db
from app.core.errors import register_error_handlers
from app.core.files import ensure_dirs, safe_download_filename, url_to_fs_path
from app.core.schema import init_db, migrate_legacy_log_tables
from app.core.templating import templates
from app.core.validators import validate_yyyy_mm_dd
from app.features.actors import service as actors_service
from app.features.actors.router import router as actors_router
from app.features.auth.router import router as auth_router
from app.features.teachers import service as teachers_service
from app.features.teachers.router import router as teachers_router
from app.features.users import service as users_service
from app.features.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    await init_db()
    await migrate_legacy_log_tables()
    async with open_db() as db:
        await actors_service.normalize_actor_data(db)
        await users_service.ensure_default_admin(db)
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
register_error_handlers(app)
app.include_router(actors_router)
app.include_router(users_router)
app.include_router(teachers_router)
app.include_router(auth_router)


@app.middleware("http")
async def kiosk_mode_guard(request: Request, call_next):
    path = request.url.path

    # 메인/관리 페이지로 들어오면 kiosk 모드 자동 해제
    release_paths = ["/", "/attendance", "/login", "/logout"]
    if path in release_paths:
        request.session["kiosk_mode"] = False

    # static, login/logout, kiosk 관련 경로는 허용
    allowed_prefixes = [
        "/static",
        "/login",
        "/logout",
        "/attendance/kiosk",
    ]

    kiosk_mode = request.session.get("kiosk_mode", False)

    if kiosk_mode:
        is_allowed = any(path.startswith(prefix) for prefix in allowed_prefixes)
        if not is_allowed:
            return RedirectResponse(url="/attendance/kiosk", status_code=303)

    response = await call_next(request)
    return response


app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)


# -------------------------
# 공통 유틸
# -------------------------


def actor_url(actor_id: int, tab: str | None = None) -> str:
    if tab:
        return f"/actors/{actor_id}?tab={tab}"
    return f"/actors/{actor_id}"


def _get_blank_layout(prs: Presentation):
    # 보통 6번이 blank 레이아웃인 경우가 많음
    # 없으면 마지막 레이아웃 사용
    try:
        return prs.slide_layouts[6]
    except Exception:
        return prs.slide_layouts[len(prs.slide_layouts) - 1]
    
def _copy_slide_contents(source_slide, dest_slide):
    for shape in source_slide.shapes:
        newel = deepcopy(shape.element)
        dest_slide.shapes._spTree.insert_element_before(newel, 'p:extLst')

def merge_pptx_files(input_paths: list[str], output_path: str):
    if not input_paths:
        raise ValueError("병합할 PPTX 파일이 없습니다.")

    merged = Presentation()
    blank_layout = _get_blank_layout(merged)

    # 기본으로 들어있는 첫 슬라이드 제거 시도
    if len(merged.slides) > 0:
        try:
            slide_id_list = merged.slides._sldIdLst
            slides = list(slide_id_list)
            slide_id_list.remove(slides[0])
        except Exception:
            pass

    for pptx_path in input_paths:
        src = Presentation(pptx_path)

        for src_slide in src.slides:
            new_slide = merged.slides.add_slide(blank_layout)
            _copy_slide_contents(src_slide, new_slide)

    merged.save(output_path)


    


# -------------------------
# DB 초기화
# -------------------------


@app.get("/where", response_class=PlainTextResponse)
def where():
    return "YOU ARE SEEING: main.py (actor_db)"


# -------------------------
# 관리자 계정 / 선생님 관리
# -------------------------


async def get_all_lessons_for_attendance():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT
                tl.id,
                tl.lesson_name,
                tl.lesson_days,
                tl.teacher_user_id,
                u.display_name AS teacher_name
            FROM teacher_lessons tl
            JOIN users u
              ON u.id = tl.teacher_user_id
            ORDER BY
                CASE WHEN tl.lesson_name IS NULL OR tl.lesson_name = '' THEN 1 ELSE 0 END,
                tl.lesson_name ASC,
                tl.id DESC
        """)
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_lesson_for_user(current_user, lesson_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if current_user["role"] == "teacher":
            cur = await db.execute("""
                SELECT
                    tl.id,
                    tl.lesson_name,
                    tl.lesson_days,
                    tl.teacher_user_id
                FROM teacher_lessons tl
                WHERE tl.id = ?
                  AND tl.teacher_user_id = ?
            """, (lesson_id, current_user["id"]))
        else:
            cur = await db.execute("""
                SELECT
                    tl.id,
                    tl.lesson_name,
                    tl.lesson_days,
                    tl.teacher_user_id
                FROM teacher_lessons tl
                WHERE tl.id = ?
            """, (lesson_id,))

        row = await cur.fetchone()

    return dict(row) if row else None


async def get_lesson_actors_with_attendance(lesson_id: int, attendance_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
            SELECT
                a.id,
                a.name,
                a.gender,
                a.birth_year,
                a.phone_last4,
                al.status,
                al.phone_input,
                al.feedback
            FROM lesson_actor_assignments la
            JOIN actors a
              ON a.id = la.actor_id
            LEFT JOIN attendance_logs al
              ON al.lesson_id = la.lesson_id
             AND al.actor_id = la.actor_id
             AND al.attendance_date = ?
            WHERE la.lesson_id = ?
            ORDER BY a.name ASC, a.id DESC
        """, (attendance_date, lesson_id))

        rows = await cur.fetchall()

    return [dict(r) for r in rows]

async def find_actor_by_phone_last4_in_lesson(lesson_id: int, phone_last4: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
            SELECT
                a.id,
                a.name,
                a.phone_last4
            FROM lesson_actor_assignments la
            JOIN actors a
              ON a.id = la.actor_id
            WHERE la.lesson_id = ?
              AND a.phone_last4 = ?
            ORDER BY a.name ASC, a.id DESC
        """, (lesson_id, phone_last4))

        rows = await cur.fetchall()

    return [dict(r) for r in rows]

async def get_today_attendance_candidates():
    today_short = get_korean_weekday_short()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
            SELECT
                tl.id AS lesson_id,
                tl.lesson_name,
                tl.lesson_days,
                a.id AS actor_id,
                a.name,
                a.phone_last4
            FROM teacher_lessons tl
            JOIN lesson_actor_assignments la
              ON la.lesson_id = tl.id
            JOIN actors a
              ON a.id = la.actor_id
            ORDER BY tl.id DESC, a.name ASC
        """)
        rows = await cur.fetchall()

    results = []
    seen = set()

    for row in rows:
        row = dict(row)

        if not lesson_matches_today(row.get("lesson_days", "")):
            continue

        # 같은 배우가 오늘 여러 수업에 중복 연결되어 있더라도 1번만 보여주기
        dedupe_key = row["actor_id"]
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        row["today_short"] = today_short
        results.append(row)

    return results


async def find_today_actor_by_phone_last4(phone_last4: str):
    candidates = await get_today_attendance_candidates()
    phone_last4 = "".join(ch for ch in str(phone_last4 or "") if ch.isdigit())[:4]

    matched = []
    for row in candidates:
        saved = "".join(ch for ch in str(row.get("phone_last4") or "") if ch.isdigit())[:4]
        if saved and saved == phone_last4:
            matched.append(row)

    return matched


# -------------------------
# 메인(검색 포함)
# -------------------------


def get_korean_weekday_short() -> str:
    weekday_map = {
        0: "월",
        1: "화",
        2: "수",
        3: "목",
        4: "금",
        5: "토",
        6: "일",
    }
    return weekday_map[datetime.now().weekday()]


def lesson_matches_today(lesson_days: str) -> bool:
    if not lesson_days:
        return False

    today_short = get_korean_weekday_short()
    raw = str(lesson_days).strip()

    normalized = (
        raw.replace("요일", "")
           .replace("/", ",")
           .replace("|", ",")
           .replace("·", ",")
           .replace(" ", "")
    )

    tokens = [x for x in normalized.split(",") if x]

    if today_short in tokens:
        return True

    # 혹시 "월수금" 같이 붙어있는 경우도 대응
    if today_short in normalized:
        return True

    return False


@app.get("/attendance", response_class=HTMLResponse)
async def attendance_page(
    request: Request,
    lesson_id: str | None = None,
    attendance_date: str | None = None,
):
    current_user = await require_login_user(request)

    lesson_id = (lesson_id or "").strip()
    attendance_date = (attendance_date or datetime.now().strftime("%Y-%m-%d")).strip()

    try:
        attendance_date = validate_yyyy_mm_dd(attendance_date)
    except Exception:
        attendance_date = datetime.now().strftime("%Y-%m-%d")

    if current_user["role"] == "teacher":
        lessons = await get_teacher_lessons(current_user["id"])
        lessons = [
            {
                "id": x["id"],
                "lesson_name": x["lesson_name"],
                "lesson_days": x["lesson_days"],
                "teacher_user_id": x["teacher_user_id"],
                "teacher_name": current_user["display_name"],
            }
            for x in lessons
        ]
    else:
        lessons = await get_all_lessons_for_attendance()

    selected_lesson = None
    actors = []

    if not lesson_id and lessons:
        lesson_id = str(lessons[0]["id"])

    if lesson_id:
        try:
            lesson_id_int = int(lesson_id)
        except Exception:
            lesson_id_int = None

        if lesson_id_int:
            selected_lesson = await get_lesson_for_user(current_user, lesson_id_int)
            if selected_lesson:
                actors = await get_lesson_actors_with_attendance(lesson_id_int, attendance_date)

    return templates.TemplateResponse(
        "attendance.html",
        {
            "request": request,
            "current_user": current_user,
            "lessons": lessons,
            "selected_lesson": selected_lesson,
            "lesson_id": lesson_id,
            "attendance_date": attendance_date,
            "actors": actors,
        }
    )


@app.post("/attendance/save")
async def attendance_save(request: Request):
    current_user = await require_login_user(request)
    form = await request.form()

    lesson_id_raw = str(form.get("lesson_id") or "").strip()
    attendance_date = str(form.get("attendance_date") or "").strip()

    if not lesson_id_raw:
        raise HTTPException(status_code=400, detail="수업을 선택해주세요.")

    lesson_id = int(lesson_id_raw)
    attendance_date = validate_yyyy_mm_dd(attendance_date)

    selected_lesson = await get_lesson_for_user(current_user, lesson_id)
    if not selected_lesson:
        raise HTTPException(status_code=403, detail="해당 수업 접근 권한이 없습니다.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
            SELECT
                a.id,
                a.phone_last4
            FROM lesson_actor_assignments la
            JOIN actors a
              ON a.id = la.actor_id
            WHERE la.lesson_id = ?
        """, (lesson_id,))
        lesson_actors = await cur.fetchall()

        for actor in lesson_actors:
            actor_id = actor["id"]
            saved_last4 = "".join(ch for ch in str(actor["phone_last4"] or "") if ch.isdigit())[:4]

            phone_input = str(form.get(f"phone_input_{actor_id}") or "").strip()
            phone_input_digits = "".join(ch for ch in phone_input if ch.isdigit())[:4]

            status = str(form.get(f"status_{actor_id}") or "").strip()
            feedback = str(form.get(f"feedback_{actor_id}") or "").strip()

            # 상태를 안 골랐는데 번호가 맞으면 자동 출석
            if not status:
                if saved_last4 and phone_input_digits and saved_last4 == phone_input_digits:
                    status = "출석"
                else:
                    status = "미체크"

            # 1) 출결 저장
            await db.execute("""
                INSERT INTO attendance_logs (
                    lesson_id, actor_id, attendance_date, status,
                    phone_input, feedback, checked_by_user_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lesson_id, actor_id, attendance_date)
                DO UPDATE SET
                    status = excluded.status,
                    phone_input = excluded.phone_input,
                    feedback = excluded.feedback,
                    checked_by_user_id = excluded.checked_by_user_id,
                    updated_at = excluded.updated_at
            """, (
                lesson_id,
                actor_id,
                attendance_date,
                status,
                phone_input_digits,
                feedback,
                current_user["id"],
                now,
                now,
            ))

            # 2) 피드백이 있으면 트레이닝 피드백(class_logs)에도 자동 기록
            if feedback:
                lesson_name = ""
                cur2 = await db.execute("""
                    SELECT lesson_name
                    FROM teacher_lessons
                    WHERE id = ?
                """, (lesson_id,))
                lesson_row = await cur2.fetchone()
                if lesson_row and lesson_row[0]:
                    lesson_name = str(lesson_row[0]).strip()

                classlog_content = feedback
                if lesson_name:
                    classlog_content = f"[{lesson_name}] {feedback}"

                # 같은 날짜 + 같은 내용이 이미 있으면 중복 저장 방지
                cur3 = await db.execute("""
                    SELECT id
                    FROM class_logs
                    WHERE actor_id = ?
                      AND meet_date = ?
                      AND content = ?
                    LIMIT 1
                """, (
                    actor_id,
                    attendance_date,
                    classlog_content
                ))
                existing_classlog = await cur3.fetchone()

                if not existing_classlog:
                    await db.execute("""
                        INSERT INTO class_logs (
                            actor_id, meet_date, content, created_at
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        actor_id,
                        attendance_date,
                        classlog_content,
                        now,
                    ))

        await db.commit()

    return RedirectResponse(
        url=f"/attendance?lesson_id={lesson_id}&attendance_date={quote(attendance_date)}",
        status_code=303
    )

@app.get("/attendance/kiosk", response_class=HTMLResponse)
async def attendance_kiosk_page(request: Request):
    current_user = await require_admin(request)
    request.session["kiosk_mode"] = True

    today_short = get_korean_weekday_short()
    today_candidates = await get_today_attendance_candidates()

    return templates.TemplateResponse(
        "attendance_kiosk.html",
        {
            "request": request,
            "current_user": current_user,
            "today_str": datetime.now().strftime("%Y-%m-%d"),
            "today_short": today_short,
            "today_candidates_count": len(today_candidates),
        }
    )

@app.post("/attendance/kiosk/check")
async def attendance_kiosk_check(request: Request):
    current_user = await require_admin(request)
    
    form = await request.form()

    phone_last4 = "".join(ch for ch in str(form.get("phone_last4") or "").strip() if ch.isdigit())[:4]

    if len(phone_last4) != 4:
        return {
            "ok": False,
            "message": "4자리를 입력해주세요."
        }

    matched_actors = await find_today_actor_by_phone_last4(phone_last4)

    if not matched_actors:
        return {
            "ok": False,
            "message": "오늘 출석 대상자 중 일치하는 배우가 없습니다."
        }

    if len(matched_actors) > 1:
        names = ", ".join([x["name"] for x in matched_actors[:3]])
        return {
            "ok": False,
            "message": f"번호가 중복됩니다. 관리자 확인 필요 ({names})"
        }

    actor = matched_actors[0]
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
            SELECT id, status
            FROM attendance_logs
            WHERE lesson_id = ?
              AND actor_id = ?
              AND attendance_date = ?
        """, (actor["lesson_id"], actor["actor_id"], today))
        existing = await cur.fetchone()

        if existing and existing["status"] == "출석":
            return {
                "ok": True,
                "message": f"{actor['name']} 이미 출석 처리되었습니다.",
                "actor_name": actor["name"],
                "status": "already"
            }

        await db.execute("""
            INSERT INTO attendance_logs (
                lesson_id, actor_id, attendance_date, status,
                phone_input, feedback, checked_by_user_id,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lesson_id, actor_id, attendance_date)
            DO UPDATE SET
                status = excluded.status,
                phone_input = excluded.phone_input,
                checked_by_user_id = excluded.checked_by_user_id,
                updated_at = excluded.updated_at
        """, (
            actor["lesson_id"],
            actor["actor_id"],
            today,
            "출석",
            phone_last4,
            "",
            current_user["id"],
            now,
            now,
        ))
        await db.commit()

    return {
        "ok": True,
        "message": f"{actor['name']} 출석 완료",
        "actor_name": actor["name"],
        "status": "checked"
    }

@app.get("/attendance/kiosk/exit")
async def attendance_kiosk_exit(request: Request):
    await require_admin(request)
    request.session["kiosk_mode"] = False
    return RedirectResponse(url="/attendance", status_code=303)

@app.get("/download/merged-compcards/pdf")
async def download_merged_compcards_pdf(
    q: str | None = None,
    m: str | None = None,
    ai_query: str | None = None,
    gender: str | None = None,
    height_group: str | None = None,
    birth_group: str | None = None,
    sort: str | None = None,
    status_filter: str | None = None,
):
    actors, _, _ = await get_filtered_actors(
        q=q or "",
        m=m or "",
        ai_query=ai_query or "",
        gender=gender or "",
        height_group=height_group or "",
        birth_group=birth_group or "",
        sort=sort or "",
        status_filter=status_filter or "",
    )
    pdf_paths = []
    skipped = []

    for actor in actors:
        compcard_url = actor["compcard_path"] if "compcard_path" in actor.keys() else None
        preview_url = actor["compcard_preview_path"] if "compcard_preview_path" in actor.keys() else None

        candidate_urls = []
        if compcard_url:
            candidate_urls.append(compcard_url)
        if preview_url and preview_url != compcard_url:
            candidate_urls.append(preview_url)

        found_pdf = None

        for url in candidate_urls:
            fs_path = url_to_fs_path(url)

            if os.path.exists(fs_path) and fs_path.lower().endswith(".pdf"):
                found_pdf = fs_path
                break

        if found_pdf:
            pdf_paths.append(found_pdf)
        else:
            skipped.append(actor["name"])

    if not pdf_paths:
        return PlainTextResponse("통합 가능한 PDF 파일이 없습니다.", status_code=404)

    ensure_dirs()

    output_filename = safe_download_filename("merged_compcards", "pdf")
    output_path = os.path.join(MERGED_DIR, output_filename)

    writer = PdfWriter()

    try:
        for pdf_path in pdf_paths:
            writer.append(pdf_path)

        with open(output_path, "wb") as f:
            writer.write(f)

    except Exception as e:
        return PlainTextResponse(f"PDF 병합 중 오류 발생: {str(e)}", status_code=500)

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=output_filename,
    )

@app.post("/download/selected-compcards/pdf")
async def download_selected_compcards_pdf(actor_ids: list[int] = Form(...)):
    ensure_dirs()

    placeholders = ",".join(["?"] * len(actor_ids))
    query = f"""
        SELECT id, name, compcard_path, compcard_preview_path
        FROM actors
        WHERE id IN ({placeholders})
        ORDER BY id DESC
    """

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, actor_ids)
        actors = await cur.fetchall()

    pdf_paths = []

    for actor in actors:
        compcard_url = actor["compcard_path"] if "compcard_path" in actor.keys() else None
        preview_url = actor["compcard_preview_path"] if "compcard_preview_path" in actor.keys() else None

        candidate_urls = []
        if compcard_url:
            candidate_urls.append(compcard_url)
        if preview_url and preview_url != compcard_url:
            candidate_urls.append(preview_url)

        found_pdf = None
        for url in candidate_urls:
            if not url:
                continue
            fs_path = url_to_fs_path(url)
            if os.path.exists(fs_path) and fs_path.lower().endswith(".pdf"):
                found_pdf = fs_path
                break

        if found_pdf:
            pdf_paths.append(found_pdf)

    if not pdf_paths:
        return PlainTextResponse("선택한 배우 중 다운로드 가능한 PDF가 없습니다.", status_code=404)

    writer = PdfWriter()
    output_filename = f"selected_compcards_{uuid.uuid4().hex[:8]}.pdf"
    output_path = os.path.join(MERGED_DIR, output_filename)

    try:
        for pdf_path in pdf_paths:
            writer.append(pdf_path)

        with open(output_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        return PlainTextResponse(f"선택 PDF 병합 중 오류 발생: {str(e)}", status_code=500)

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename="선택컴카드.pdf"
    )

# -------------------------
# 배우 추가/상세/수정/삭제
# -------------------------


# ✅ 핵심: tab 쿼리로 탭 유지 (앵커 제거)


# -------------------------
# 수업일지 항목 CRUD
# -------------------------


@app.get("/actors/{actor_id}/classlogs/new")
async def classlog_new(request: Request, actor_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    return templates.TemplateResponse("classlog_form.html", {
        "request": request, "actor_id": actor_id, "mode": "new", "item": None
    })


@app.post("/actors/{actor_id}/classlogs/new")
async def classlog_new_post(request: Request, actor_id: int, meet_date: str = Form(...), content: str = Form(...)):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    now = datetime.now().isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO class_logs (actor_id, meet_date, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (actor_id, meet_date, content, now))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "classlog"), status_code=303)


@app.get("/actors/{actor_id}/classlogs/{log_id}/edit")
async def classlog_edit(request: Request, actor_id: int, log_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM class_logs WHERE id=? AND actor_id=?", (log_id, actor_id))
        item = await cur.fetchone()
    if not item:
        return RedirectResponse(actor_url(actor_id, "classlog"), status_code=303)
    return templates.TemplateResponse("classlog_form.html", {
        "request": request, "actor_id": actor_id, "mode": "edit", "item": item
    })


@app.post("/actors/{actor_id}/classlogs/{log_id}/edit")
async def classlog_edit_post(request: Request, actor_id: int, log_id: int, meet_date: str = Form(...), content: str = Form(...)):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE class_logs SET meet_date=?, content=? WHERE id=? AND actor_id=?",
            (meet_date, content, log_id, actor_id)
        )
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "classlog"), status_code=303)


@app.post("/actors/{actor_id}/classlogs/{log_id}/delete")
async def classlog_delete(request: Request, actor_id: int, log_id: int):
    current_user = await require_record_delete_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM class_logs WHERE id=? AND actor_id=?", (log_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "classlog"), status_code=303)


# -------------------------
# 오디션 항목 CRUD
# -------------------------


@app.get("/actors/{actor_id}/auditions/new")
async def audition_new(request: Request, actor_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    return templates.TemplateResponse("audition_form.html", {
        "request": request, "actor_id": actor_id, "mode": "new", "item": None
    })


@app.post("/actors/{actor_id}/auditions/new")
async def audition_new_post(request: Request, actor_id: int, aud_date: str = Form(...), content: str = Form(...)):
    current_user = await require_actor_edit_permission(request, actor_id)
    aud_date = validate_yyyy_mm_dd(aud_date)
    now = datetime.now().isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO auditions (actor_id, aud_date, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (actor_id, aud_date, content, now))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "auditions"), status_code=303)


@app.get("/actors/{actor_id}/auditions/{aud_id}/edit")
async def audition_edit(request: Request, actor_id: int, aud_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM auditions WHERE id=? AND actor_id=?", (aud_id, actor_id))
        item = await cur.fetchone()
    if not item:
        return RedirectResponse(actor_url(actor_id, "auditions"), status_code=303)
    return templates.TemplateResponse("audition_form.html", {
        "request": request, "actor_id": actor_id, "mode": "edit", "item": item
    })


@app.post("/actors/{actor_id}/auditions/{aud_id}/edit")
async def audition_edit_post(request: Request, actor_id: int, aud_id: int, aud_date: str = Form(...), content: str = Form(...)):
    current_user = await require_actor_edit_permission(request, actor_id)
    aud_date = validate_yyyy_mm_dd(aud_date)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE auditions SET aud_date=?, content=? WHERE id=? AND actor_id=?",
            (aud_date, content, aud_id, actor_id)
        )
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "auditions"), status_code=303)


@app.post("/actors/{actor_id}/auditions/{aud_id}/delete")
async def audition_delete(request: Request, actor_id: int, aud_id: int):
    current_user = await require_record_delete_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM auditions WHERE id=? AND actor_id=?", (aud_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "auditions"), status_code=303)


# -------------------------
# 캐스팅관리 기록 항목 CRUD
# -------------------------


@app.get("/actors/{actor_id}/casting-management/new")
async def casting_mgmt_new(request: Request, actor_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    return templates.TemplateResponse("casting_management_form.html", {
        "request": request, "actor_id": actor_id, "mode": "new", "item": None
    })


@app.post("/actors/{actor_id}/casting-management/new")
async def casting_mgmt_new_post(
    request: Request,
    actor_id: int,
    meet_date: str = Form(...),
    content: str = Form(...),
):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    now = datetime.now().isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO casting_management_logs (actor_id, meet_date, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (actor_id, meet_date, content, now))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "casting_management"), status_code=303)


@app.get("/actors/{actor_id}/casting-management/{item_id}/edit")
async def casting_mgmt_edit(request: Request, actor_id: int, item_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
        SELECT * FROM casting_management_logs WHERE id=? AND actor_id=?
        """, (item_id, actor_id))
        item = await cur.fetchone()
    if not item:
        return RedirectResponse(actor_url(actor_id, "casting_management"), status_code=303)

    return templates.TemplateResponse("casting_management_form.html", {
        "request": request, "actor_id": actor_id, "mode": "edit", "item": item
    })


@app.post("/actors/{actor_id}/casting-management/{item_id}/edit")
async def casting_mgmt_edit_post(
    request: Request,
    actor_id: int,
    item_id: int,
    meet_date: str = Form(...),
    content: str = Form(...),
):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE casting_management_logs
        SET meet_date=?, content=?
        WHERE id=? AND actor_id=?
        """, (meet_date, content, item_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "casting_management"), status_code=303)


@app.post("/actors/{actor_id}/casting-management/{item_id}/delete")
async def casting_mgmt_delete(request: Request, actor_id: int, item_id: int):
    current_user = await require_record_delete_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        DELETE FROM casting_management_logs WHERE id=? AND actor_id=?
        """, (item_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "casting_management"), status_code=303)


# -------------------------
# 캐스팅 미팅 기록 항목 CRUD
# -------------------------


@app.get("/actors/{actor_id}/casting-meetings/new")
async def casting_meeting_new(request: Request, actor_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    return templates.TemplateResponse("casting_meeting_form.html", {
        "request": request, "actor_id": actor_id, "mode": "new", "item": None
    })


@app.post("/actors/{actor_id}/casting-meetings/new")
async def casting_meeting_new_post(
    request: Request,
    actor_id: int,
    meet_date: str = Form(...),
    content: str = Form(...),
):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    now = datetime.now().isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO casting_meetings (actor_id, meet_date, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (actor_id, meet_date, content, now))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "casting_meetings"), status_code=303)


@app.get("/actors/{actor_id}/casting-meetings/{item_id}/edit")
async def casting_meeting_edit(request: Request, actor_id: int, item_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
        SELECT * FROM casting_meetings WHERE id=? AND actor_id=?
        """, (item_id, actor_id))
        item = await cur.fetchone()
    if not item:
        return RedirectResponse(actor_url(actor_id, "casting_meetings"), status_code=303)

    return templates.TemplateResponse("casting_meeting_form.html", {
        "request": request, "actor_id": actor_id, "mode": "edit", "item": item
    })


@app.post("/actors/{actor_id}/casting-meetings/{item_id}/edit")
async def casting_meeting_edit_post(
    request: Request,
    actor_id: int,
    item_id: int,
    meet_date: str = Form(...),
    content: str = Form(...),
):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE casting_meetings
        SET meet_date=?, content=?
        WHERE id=? AND actor_id=?
        """, (meet_date, content, item_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "casting_meetings"), status_code=303)


@app.post("/actors/{actor_id}/casting-meetings/{item_id}/delete")
async def casting_meeting_delete(request: Request, actor_id: int, item_id: int):
    current_user = await require_record_delete_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        DELETE FROM casting_meetings WHERE id=? AND actor_id=?
        """, (item_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "casting_meetings"), status_code=303)


# -------------------------
# 첫 미팅 기록 항목 CRUD
# -------------------------


@app.get("/actors/{actor_id}/first-meetings/new")
async def first_meeting_new(request: Request, actor_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    return templates.TemplateResponse("first_meeting_form.html", {
        "request": request, "actor_id": actor_id, "mode": "new", "item": None
    })


@app.post("/actors/{actor_id}/first-meetings/new")
async def first_meeting_new_post(
    request: Request,
    actor_id: int,
    meet_date: str = Form(...),
    content: str = Form(...),
):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    now = datetime.now().isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO first_meetings (actor_id, meet_date, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (actor_id, meet_date, content, now))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "first_meeting"), status_code=303)


@app.get("/actors/{actor_id}/first-meetings/{item_id}/edit")
async def first_meeting_edit(request: Request, actor_id: int, item_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
        SELECT * FROM first_meetings WHERE id=? AND actor_id=?
        """, (item_id, actor_id))
        item = await cur.fetchone()
    if not item:
        return RedirectResponse(actor_url(actor_id, "first_meeting"), status_code=303)

    return templates.TemplateResponse("first_meeting_form.html", {
        "request": request, "actor_id": actor_id, "mode": "edit", "item": item
    })


@app.post("/actors/{actor_id}/first-meetings/{item_id}/edit")
async def first_meeting_edit_post(
    request: Request,
    actor_id: int,
    item_id: int,
    meet_date: str = Form(...),
    content: str = Form(...),
):
    current_user = await require_actor_edit_permission(request, actor_id)
    meet_date = validate_yyyy_mm_dd(meet_date)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE first_meetings
        SET meet_date=?, content=?
        WHERE id=? AND actor_id=?
        """, (meet_date, content, item_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "first_meeting"), status_code=303)


@app.post("/actors/{actor_id}/first-meetings/{item_id}/delete")
async def first_meeting_delete(request: Request, actor_id: int, item_id: int):
    current_user = await require_record_delete_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        DELETE FROM first_meetings WHERE id=? AND actor_id=?
        """, (item_id, actor_id))
        await db.commit()
    return RedirectResponse(actor_url(actor_id, "first_meeting"), status_code=303)


# -------------------------
# Phase 3 전환용: 아직 main.py에 남은 라우트가 쓰는 다른 기능의 service
# -------------------------

async def get_teacher_management_rows():
    async with open_db() as db:
        return await teachers_service.get_teacher_management_rows(db)


async def get_teacher_lessons(teacher_user_id: int):
    async with open_db() as db:
        return await teachers_service.get_teacher_lessons(db, teacher_user_id)


async def get_filtered_actors(q="", m="", ai_query="", gender="", height_group="", birth_group="", sort="", status_filter=""):
    async with open_db() as db:
        f = actors_service.make_filters(q, m, gender, height_group, birth_group, sort, status_filter)
        return await actors_service.search_actors(db, f, (ai_query or "").strip())
