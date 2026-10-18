import math
import os
import re
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from urllib.parse import quote

import aiosqlite
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pptx import Presentation
from pypdf import PdfWriter
from starlette.middleware.sessions import SessionMiddleware

from app.core.auth import (
    can_create_actor,
    get_current_user,
    require_actor_edit_permission,
    require_admin_legacy as require_admin,
    require_admin_or_staff_legacy as require_admin_or_staff,
    require_login_user,
    require_record_delete_permission,
    teacher_can_access_actor,
)
from app.core.config import (
    DB_PATH,
    MERGED_DIR,
    SECRET_KEY,
    SESSION_COOKIE_NAME,
    SESSION_HTTPS_ONLY,
    SESSION_MAX_AGE,
    STATIC_DIR,
    UPLOAD_DIR,
)
from app.core.database import open_db
from app.core.errors import register_error_handlers
from app.features.teachers.router import router as teachers_router
from app.features.auth.router import router as auth_router
from app.core.files import (
    ensure_dirs,
    make_thumbnail_from_url,
    normalize_uploadfiles,
    safe_download_filename,
    save_upload,
    try_remove_by_url,
    url_to_fs_path,
)
from app.core.schema import init_db, migrate_legacy_log_tables
from app.core.security import hash_password
from app.core.templating import templates
from app.core.validators import clean_birth_year, clean_date, validate_yyyy_mm_dd
from app.features.teachers import service as teachers_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    await init_db()
    await migrate_legacy_log_tables()
    await normalize_actor_data()
    await ensure_default_admin()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
register_error_handlers(app)
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


def _find_soffice_exe() -> str | None:
    p = shutil.which("soffice")
    if p:
        return p
    candidates = ["/usr/bin/soffice", "/usr/local/bin/soffice"]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def _make_ppt_preview_via_libreoffice(ppt_public_url: str) -> str | None:
    ext = os.path.splitext(ppt_public_url)[1].lower()
    if ext not in [".ppt", ".pptx"]:
        return None

    ppt_path = url_to_fs_path(ppt_public_url)
    if not os.path.exists(ppt_path):
        return None

    soffice = _find_soffice_exe()
    if not soffice:
        return None

    out_dir = os.path.join(UPLOAD_DIR, f"ppt_preview_{uuid.uuid4().hex}")
    os.makedirs(out_dir, exist_ok=True)

    try:
        cmd = [
            soffice,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--nodefault",
            "--nofirststartwizard",
            "--convert-to",
            "png",
            "--outdir",
            os.path.abspath(out_dir),
            os.path.abspath(ppt_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        png_files = sorted([fn for fn in os.listdir(out_dir) if fn.lower().endswith(".png")])
        if not png_files:
            return None

        first_png_path = os.path.join(out_dir, png_files[0])

        preview_filename = f"compcard_preview_{uuid.uuid4().hex}.png"
        preview_save_path = os.path.join(UPLOAD_DIR, preview_filename)

        with open(first_png_path, "rb") as src, open(preview_save_path, "wb") as dst:
            dst.write(src.read())

        shutil.rmtree(out_dir, ignore_errors=True)
        return f"/static/uploads/{preview_filename}"

    except Exception as e:
        print("PPT PREVIEW ERROR:", e)
        shutil.rmtree(out_dir, ignore_errors=True)
        return None


def _make_ppt_first_slide_preview(ppt_public_url: str) -> str | None:
    return _make_ppt_preview_via_libreoffice(ppt_public_url)


    
async def normalize_actor_data():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id, birth_year, contract_date, contract_end_date
            FROM actors
        """)
        rows = await cur.fetchall()

        for row in rows:
            actor_id = row["id"]

            birth_year_value = clean_birth_year(row["birth_year"])
            clean_contract_date = clean_date(row["contract_date"])
            clean_contract_end_date = clean_date(row["contract_end_date"])

            if clean_contract_date and not clean_contract_end_date:
                try:
                    start_date = datetime.strptime(clean_contract_date, "%Y-%m-%d")
                    next_year = start_date.replace(year=start_date.year + 1)
                    clean_contract_end_date = (next_year - timedelta(days=1)).strftime("%Y-%m-%d")
                except ValueError:
                    clean_contract_end_date = None

            await db.execute("""
                UPDATE actors
                SET birth_year=?,
                    contract_date=?,
                    contract_end_date=?
                WHERE id=?
            """, (
                birth_year_value,
                clean_contract_date,
                clean_contract_end_date,
                actor_id
            ))

        await db.commit()


async def get_user_by_id(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id, username, display_name, role, is_active, created_at
            FROM users
            WHERE id = ?
        """, (user_id,))
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_admin_users_page_context(current_user, error: str = "", success: str = ""):
    users = await get_all_users()
    teacher_rows = await get_teacher_management_rows()
    all_actors = await get_all_actors_simple()
    return {
        "current_user": current_user,
        "users": users,
        "teacher_rows": teacher_rows,
        "all_actors": all_actors,
        "error": error,
        "success": success,
    }


# -------------------------
# DB 초기화
# -------------------------

async def ensure_default_admin():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        row = await cur.fetchone()

        if row:
            return

        await db.execute("""
            INSERT INTO users (username, password_hash, display_name, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "admin",
            hash_password("1234"),
            "최고관리자",
            "admin",
            1,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        await db.commit()
        print("기본 관리자 계정 생성 완료: admin / 1234")


@app.get("/where", response_class=PlainTextResponse)
def where():
    return "YOU ARE SEEING: main.py (actor_db)"


# -------------------------
# 관리자 계정 / 선생님 관리
# -------------------------

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id, username, display_name, role, is_active, created_at
            FROM users
            ORDER BY
                CASE role
                    WHEN 'admin' THEN 0
                    WHEN 'staff' THEN 1
                    WHEN 'teacher' THEN 2
                    ELSE 9
                END,
                created_at DESC,
                id DESC
        """)
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_all_actors_simple():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id, name, teacher_user_id
            FROM actors
            ORDER BY name ASC, id DESC
        """)
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


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

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    current_user = await require_admin(request)
    users = await get_all_users()
    teacher_rows = await get_teacher_management_rows()
    all_actors = await get_all_actors_simple()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "current_user": current_user,
            "users": users,
            "teacher_rows": teacher_rows,
            "all_actors": all_actors,
            "error": "",
            "success": request.query_params.get("success", ""),
        }
    )


@app.post("/admin/users/new", response_class=HTMLResponse)
async def admin_users_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(...),
):
    current_user = await require_admin(request)

    username = (username or "").strip()
    password = (password or "").strip()
    password_confirm = (password_confirm or "").strip()
    display_name = (display_name or "").strip()
    role = (role or "").strip()

    if not username or not display_name or not password:
        users = await get_all_users()
        teacher_rows = await get_teacher_management_rows()
        all_actors = await get_all_actors_simple()
        return templates.TemplateResponse(
            "admin_users.html",
            {
                "request": request,
                "current_user": current_user,
                "users": users,
                "teacher_rows": teacher_rows,
                "all_actors": all_actors,
                "error": "아이디, 비밀번호, 이름은 필수입니다.",
                "success": "",
            }
        )

    if len(username) < 4:
        users = await get_all_users()
        teacher_rows = await get_teacher_management_rows()
        all_actors = await get_all_actors_simple()
        return templates.TemplateResponse(
            "admin_users.html",
            {
                "request": request,
                "current_user": current_user,
                "users": users,
                "teacher_rows": teacher_rows,
                "all_actors": all_actors,
                "error": "아이디는 4자 이상으로 입력해주세요.",
                "success": "",
            }
        )

    if len(password) < 4:
        users = await get_all_users()
        teacher_rows = await get_teacher_management_rows()
        all_actors = await get_all_actors_simple()
        return templates.TemplateResponse(
            "admin_users.html",
            {
                "request": request,
                "current_user": current_user,
                "users": users,
                "teacher_rows": teacher_rows,
                "all_actors": all_actors,
                "error": "비밀번호는 4자 이상으로 입력해주세요.",
                "success": "",
            }
        )

    if password != password_confirm:
        users = await get_all_users()
        teacher_rows = await get_teacher_management_rows()
        all_actors = await get_all_actors_simple()
        return templates.TemplateResponse(
            "admin_users.html",
            {
                "request": request,
                "current_user": current_user,
                "users": users,
                "teacher_rows": teacher_rows,
                "all_actors": all_actors,
                "error": "비밀번호 확인이 일치하지 않습니다.",
                "success": "",
            }
        )

    if role not in ["admin", "staff", "teacher"]:
        users = await get_all_users()
        teacher_rows = await get_teacher_management_rows()
        all_actors = await get_all_actors_simple()
        return templates.TemplateResponse(
            "admin_users.html",
            {
                "request": request,
                "current_user": current_user,
                "users": users,
                "teacher_rows": teacher_rows,
                "all_actors": all_actors,
                "error": "권한 값이 올바르지 않습니다.",
                "success": "",
            }
        )

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
        exists = await cur.fetchone()

        if exists:
            users = await get_all_users()
            teacher_rows = await get_teacher_management_rows()
            all_actors = await get_all_actors_simple()
            return templates.TemplateResponse(
                "admin_users.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "users": users,
                    "teacher_rows": teacher_rows,
                    "all_actors": all_actors,
                    "error": "이미 사용 중인 아이디입니다.",
                    "success": "",
                }
            )

        cur = await db.execute("""
            INSERT INTO users (username, password_hash, display_name, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            username,
            hash_password(password),
            display_name,
            role,
            1,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        await db.commit()

        new_user_id = cur.lastrowid

        if role == "teacher":
            await db.execute("""
                INSERT OR IGNORE INTO teacher_profiles (user_id, lesson_subject, lesson_days, updated_at)
                VALUES (?, '', '', ?)
            """, (
                new_user_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            await db.commit()

    return RedirectResponse(url="/admin/users?success=created", status_code=303)


@app.post("/admin/users/{user_id}/toggle-active")
async def admin_user_toggle_active(request: Request, user_id: int):
    current_user = await require_admin(request)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
            SELECT id, username, role, is_active
            FROM users
            WHERE id = ?
        """, (user_id,))
        target = await cur.fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

        target = dict(target)

        if target["id"] == current_user["id"]:
            raise HTTPException(status_code=400, detail="현재 로그인한 본인 계정은 비활성화할 수 없습니다.")

        new_active = 0 if int(target["is_active"]) == 1 else 1

        await db.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ?
        """, (new_active, user_id))
        await db.commit()

    return RedirectResponse(url="/admin/users?success=toggled", status_code=303)

@app.post("/admin/users/{user_id}/change-role", response_class=HTMLResponse)
async def admin_user_change_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
):
    current_user = await require_admin(request)

    role = (role or "").strip()

    if role not in ["admin", "staff", "teacher"]:
        ctx = await get_admin_users_page_context(current_user, error="권한 값이 올바르지 않습니다.")
        ctx["request"] = request
        return templates.TemplateResponse("admin_users.html", ctx)

    target_user = await get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

    # 본인 권한은 여기서 변경 못 하게 막기
    if target_user["id"] == current_user["id"]:
        ctx = await get_admin_users_page_context(current_user, error="현재 로그인한 본인 계정의 권한은 변경할 수 없습니다.")
        ctx["request"] = request
        return templates.TemplateResponse("admin_users.html", ctx)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 마지막 admin 보호
        if target_user["role"] == "admin" and role != "admin":
            cur = await db.execute("""
                SELECT COUNT(*) FROM users
                WHERE role = 'admin'
            """)
            admin_count = (await cur.fetchone())[0]
            if admin_count <= 1:
                ctx = await get_admin_users_page_context(current_user, error="마지막 관리자 계정의 권한은 변경할 수 없습니다.")
                ctx["request"] = request
                return templates.TemplateResponse("admin_users.html", ctx)

        await db.execute("""
            UPDATE users
            SET role = ?
            WHERE id = ?
        """, (role, user_id))

        # teacher로 바뀌면 teacher_profiles 기본 생성
        if role == "teacher":
            await db.execute("""
                INSERT OR IGNORE INTO teacher_profiles (user_id, lesson_subject, lesson_days, updated_at)
                VALUES (?, '', '', ?)
            """, (
                user_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        await db.commit()

    return RedirectResponse(url="/admin/users?success=role_changed", status_code=303)

@app.post("/admin/users/{user_id}/reset-password", response_class=HTMLResponse)
async def admin_user_reset_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
):
    current_user = await require_admin(request)

    new_password = (new_password or "").strip()
    new_password_confirm = (new_password_confirm or "").strip()

    if len(new_password) < 4:
        ctx = await get_admin_users_page_context(current_user, error="비밀번호는 4자 이상으로 입력해주세요.")
        ctx["request"] = request
        return templates.TemplateResponse("admin_users.html", ctx)

    if new_password != new_password_confirm:
        ctx = await get_admin_users_page_context(current_user, error="비밀번호 확인이 일치하지 않습니다.")
        ctx["request"] = request
        return templates.TemplateResponse("admin_users.html", ctx)

    target_user = await get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
        """, (hash_password(new_password), user_id))
        await db.commit()

    return RedirectResponse(
        url=f"/admin/users?success=pw_reset_{quote(target_user['username'])}",
        status_code=303
    )

@app.post("/admin/users/{user_id}/delete")
async def admin_user_delete(request: Request, user_id: int):
    current_user = await require_admin(request)

    target_user = await get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

    if target_user["id"] == current_user["id"]:
        raise HTTPException(status_code=400, detail="현재 로그인한 본인 계정은 삭제할 수 없습니다.")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if target_user["role"] == "admin":
            cur = await db.execute("""
                SELECT COUNT(*) FROM users
                WHERE role = 'admin'
            """)
            admin_count = (await cur.fetchone())[0]
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="마지막 관리자 계정은 삭제할 수 없습니다.")

        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()

    return RedirectResponse(url="/admin/users?success=deleted", status_code=303)


# -------------------------
# 메인(검색 포함)
# -------------------------

AI_KEYWORD_MAP = {
    "헬스": ["헬스", "운동", "피트니스", "웨이트", "웨이트트레이닝", "자기관리"],
    "운동": ["운동", "헬스", "피트니스", "러닝", "체력", "자기관리"],
    "요가": ["요가", "필라테스", "스트레칭"],
    "필라테스": ["필라테스", "요가", "스트레칭"],
    "액션": ["액션", "무술", "검도", "태권도", "합기도", "운동"],
    "중국어": ["중국어", "중문", "mandarin", "중국어회화"],
    "영어": ["영어", "english", "영어회화"],
    "일본어": ["일본어", "japanese", "일어"],
    "승마": ["승마", "말타기"],
    "수영": ["수영", "스위밍"],
    "춤": ["춤", "댄스", "무용", "안무"],
    "노래": ["노래", "보컬", "가창"],
    "피아노": ["피아노", "건반"],
    "바이올린": ["바이올린", "현악기"],
    "축구": ["축구", "풋볼"],
    "농구": ["농구", "basketball"],
    "러닝": ["러닝", "달리기", "마라톤"],
    "자전거": ["자전거", "사이클", "라이딩"],
    "테니스": ["테니스", "라켓", "서브", "코트"],
    "골프": ["골프", "라운딩", "필드", "스윙"],
    "클라이밍": ["클라이밍", "볼더링", "암벽등반"],
    "등산": ["등산", "트래킹", "하이킹", "산행"],
    "낚시": ["낚시", "피싱", "강태공", "월척"],
    "캠핑": ["캠핑", "차박", "글램핑", "야영"],
    "서핑": ["서핑", "파도타기", "서프"],
    "스케이트보드": ["스케이트보드", "보드", "롱보드"],
    "스키": ["스키", "스노우보드", "설원"],
    "코딩": ["코딩", "프로그래밍", "개발", "소프트웨어"],
    "데이터분석": ["데이터분석", "데이터사이언스", "빅데이터"],
    "인공지능": ["인공지능", "AI", "머신러닝", "딥러닝"],
    "웹디자인": ["웹디자인", "퍼블리싱", "UIUX"],
    "영상편집": ["영상편집", "유튜브", "프리미어", "컷편집"],
    "사진": ["사진", "포토", "출사", "스냅"],
    "드로잉": ["드로잉", "일러스트", "미술", "스케치"],
    "수채화": ["수채화", "유화", "페인팅", "그림"],
    "캘리그라피": ["캘리그라피", "손글씨", "붓글씨"],
    "도예": ["도예", "도자기", "공방"],
    "가구공예": ["가구공예", "목공", "DIY"],
    "요리": ["요리", "쿠킹", "레시피", "셰프"],
    "베이킹": ["베이킹", "제과", "제빵", "디저트"],
    "바리스타": ["바리스타", "커피", "카페", "로스팅"],
    "조주": ["조주", "칵테일", "바텐더", "믹솔로지"],
    "와인": ["와인", "소믈리에", "빈티지"],
    "기타": ["기타", "어쿠스틱", "일렉기타"],
    "드럼": ["드럼", "타악기", "비트"],
    "첼로": ["첼로", "현악기", "클래식"],
    "플루트": ["플루트", "목관악기", "관현악"],
    "작곡": ["작곡", "미디", "편곡", "프로듀싱"],
    "독서": ["독서", "책", "북클럽", "라이브러리"],
    "글쓰기": ["글쓰기", "작법", "창작", "에세이"],
    "심리학": ["심리학", "마음건강", "상담"],
    "명상": ["명상", "마인드풀니스", "치유"],
    "재테크": ["재테크", "투자", "금융", "자산관리"],
    "주식": ["주식", "증권", "나스닥", "코스피"],
    "부동산": ["부동산", "임장", "경매", "내집마련"],
    "가상화폐": ["가상화폐", "코인", "블록체인", "비트코인"],
    "경제": ["경제", "경영", "시장분석"],
    "마케팅": ["마케팅", "광고", "홍보", "브랜딩"],
    "창업": ["창업", "스타트업", "비즈니스"],
    "자기계발": ["자기계발", "동기부여", "성공학"],
    "스피치": ["스피치", "발표", "웅변", "커뮤니케이션"],
    "리더십": ["리더십", "조직관리", "매니지먼트"],
    "정리정돈": ["정리정돈", "미니멀리즘", "수납"],
    "인테리어": ["인테리어", "집꾸미기", "셀프인테리어"],
    "원예": ["원예", "가드닝", "식집사", "플랜테리어"],
    "반려견": ["반려견", "강아지", "애견"],
    "반려묘": ["반려묘", "고양이", "애묘"],
    "여행": ["여행", "해외여행", "배낭여행", "투어"],
    "뷰티": ["뷰티", "메이크업", "화장품"],
    "패션": ["패션", "스타일", "코디", "OOTD"],
    "향수": ["향수", "조향", "프래그런스"],
    "피부관리": ["피부관리", "스킨케어", "에스테틱"],
    "타투": ["타투", "문신", "타투이스트"],
    "마술": ["마술", "매직", "마술사"],
    "체스": ["체스", "보드게임", "전략"],
    "바둑": ["바둑", "기원", "대국"],
    "애니메이션": ["애니메이션", "만화", "애니"],
    "영화": ["영화", "시네마", "무비"],
    "드라마": ["드라마", "시리즈", "정주행"],
    "뮤지컬": ["뮤지컬", "연극", "공연"],
    "전시회": ["전시회", "박물관", "큐레이터"],
    "천문학": ["천문학", "별자리", "관측", "우주"],
    "역사": ["역사", "한국사", "세계사", "사학"],
    "철학": ["철학", "인문학", "고전"],
    "법률": ["법률", "법학", "변호사"],
    "의학": ["의학", "건강정보", "해부학"],
    "건축": ["건축", "설계", "구조"],
    "수학": ["수학", "수리", "통계"],
    "물리학": ["물리학", "과학", "양자역학"],
    "화학": ["화학", "실험", "원소"],
    "생물학": ["생물학", "생태계", "유전학"],
    "환경": ["환경", "기후변화", "제로웨이스트"],
    "봉사활동": ["봉사활동", "기부", "사회공헌"],
    "정치": ["정치", "사회", "이슈"],
    "자동차": ["자동차", "드라이브", "카라이프"],
    "바이크": ["바이크", "오토바이", "라이딩"],
    "프라모델": ["프라모델", "건담", "조립"],
    "피규어": ["피규어", "수집", "컬렉션"],
    "드론": ["드론", "항공촬영", "무인기"],
    "원격조정": ["원격조정", "RC카", "무선조종"],
    "플라워아트": ["플라워아트", "꽃꽂이", "플로리스트"],
    "자수": ["자수", "뜨개질", "퀼트"],
    "가죽공예": ["가죽공예", "핸드메이드", "레더"],
    "사격": ["사격", "클레이사격", "슈팅"],
    "양궁": ["양궁", "활쏘기", "아처"],
    "펜싱": ["펜싱", "검술", "플뢰레"],
    "볼링": ["볼링", "스트라이크", "볼러"],
    "당구": ["당구", "포켓볼", "3쿠션"],
    "탁구": ["탁구", "핑퐁", "테이블테니스"],
    "배드민턴": ["배드민턴", "셔틀콕", "민턴"],
    "핸드볼": ["핸드볼", "구기종목"],
    "배구": ["배구", "스파이크", "발리볼"],
    "야구": ["야구", "베이스볼", "홈런"],
    "럭비": ["럭비", "미식축구"],
    "아이스하키": ["아이스하키", "스케이트"],
    "태권도": ["태권도", "품새", "격파"],
    "유도": ["유도", "메치기", "주짓수"],
    "복싱": ["복싱", "권투", "격투기"],
    "스페인어": ["스페인어", "spanish", "에스파뇰"],
    "프랑스어": ["프랑스어", "french", "불어"],
    "독일어": ["독일어", "german", "독어"]
}

NOISE_WORDS = {
    "리스트", "배우", "배우들", "찾아줘", "추천", "추천해줘",
    "가능한", "느낌", "스타일", "같은", "좀", "해줘", "보여줘"
}


def normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def parse_ai_query(ai_query: str) -> dict:
    q = normalize_text(ai_query)

    parsed = {
        "gender": "",
        "birth_group": "",
        "height_group": "",
        "keywords": [],
        "raw": ai_query.strip(),
    }

    if "여자" in q or "여성" in q:
        parsed["gender"] = "여자"
    elif "남자" in q or "남성" in q:
        parsed["gender"] = "남자"

    if "80년대" in q or "1980" in q:
        parsed["birth_group"] = "1980"
    elif "90년대" in q or "1990" in q:
        parsed["birth_group"] = "1990"
    elif "00년대" in q or "2000" in q:
        parsed["birth_group"] = "2000"
    elif "10년대" in q or "2010" in q:
        parsed["birth_group"] = "2010"

    if "150대" in q:
        parsed["height_group"] = "150"
    elif "160대" in q:
        parsed["height_group"] = "160"
    elif "170대" in q:
        parsed["height_group"] = "170"
    elif "180대" in q or "키 큰" in q:
        parsed["height_group"] = "180"

    cleaned = re.sub(r"[^\w\s가-힣]", " ", q)
    tokens = [t for t in cleaned.split() if t and t not in NOISE_WORDS]

    expanded = set()

    for token in tokens:
        if token in {"여자", "여성", "남자", "남성"}:
            continue
        if token in {"80년대", "90년대", "00년대", "10년대"}:
            continue
        if token in {"150대", "160대", "170대", "180대"}:
            continue

        matched = False
        for key, related in AI_KEYWORD_MAP.items():
            if token == key or token in key or key in token:
                expanded.update([normalize_text(x) for x in related])
                expanded.add(key)
                matched = True

        if not matched:
            expanded.add(token)

    parsed["keywords"] = list(expanded)
    return parsed


def actor_match_score(actor, parsed: dict) -> tuple[int, list[str]]:
    score = 0
    matched = []

    actor_gender = normalize_text(actor["gender"] if "gender" in actor.keys() else "")
    hobby = normalize_text(actor["hobby"] if "hobby" in actor.keys() else "")
    specialty = normalize_text(actor["specialty"] if "specialty" in actor.keys() else "")
    bio = normalize_text(actor["bio"] if "bio" in actor.keys() else "")
    school = normalize_text(actor["school"] if "school" in actor.keys() else "")
    name = normalize_text(actor["name"] if "name" in actor.keys() else "")

    full_text = " ".join([name, hobby, specialty, bio, school])

    if parsed["gender"]:
        if actor_gender == normalize_text(parsed["gender"]):
            score += 5
            matched.append(parsed["gender"])
        else:
            return (-999, [])

    birth_year = actor["birth_year"] if "birth_year" in actor.keys() else None
    if parsed["birth_group"] and birth_year:
        try:
            by = int(birth_year)
            if parsed["birth_group"] == "1980" and 1980 <= by <= 1989:
                score += 4
                matched.append("80년대생")
            elif parsed["birth_group"] == "1990" and 1990 <= by <= 1999:
                score += 4
                matched.append("90년대생")
            elif parsed["birth_group"] == "2000" and 2000 <= by <= 2009:
                score += 4
                matched.append("00년대생")
            elif parsed["birth_group"] == "2010" and 2010 <= by <= 2019:
                score += 4
                matched.append("10년대생")
            else:
                score -= 1
        except Exception:
            pass

    height_cm = actor["height_cm"] if "height_cm" in actor.keys() else None
    if parsed["height_group"] and height_cm:
        try:
            h = float(height_cm)
            if parsed["height_group"] == "150" and 150 <= h < 160:
                score += 3
                matched.append("150대")
            elif parsed["height_group"] == "160" and 160 <= h < 170:
                score += 3
                matched.append("160대")
            elif parsed["height_group"] == "170" and 170 <= h < 180:
                score += 3
                matched.append("170대")
            elif parsed["height_group"] == "180" and 180 <= h < 190:
                score += 3
                matched.append("180대")
        except Exception:
            pass

    for kw in parsed["keywords"]:
        kw = normalize_text(kw)
        if not kw:
            continue

        if kw in specialty:
            score += 4
            matched.append(kw)
        elif kw in hobby:
            score += 3
            matched.append(kw)
        elif kw in bio:
            score += 2
            matched.append(kw)
        elif kw in school:
            score += 1
            matched.append(kw)
        elif kw in full_text:
            score += 1
            matched.append(kw)

    return score, list(dict.fromkeys(matched))


def apply_ai_search(actors, ai_query: str):
    parsed = parse_ai_query(ai_query)
    scored = []

    for actor in actors:
        score, matched = actor_match_score(actor, parsed)
        if score > 0:
            scored.append((actor, score, matched))

    scored.sort(
        key=lambda x: (
            x[1],
            x[0]["birth_year"] if x[0]["birth_year"] else 0,
            x[0]["id"]
        ),
        reverse=True
    )

    return scored, parsed

async def build_actor_filters(
    q: str = "",
    m: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    status_filter: str = "",
    teacher_user_id: int | None = None,
):
    wheres = []
    params = []

    q = (q or "").strip()
    m = (m or "").strip()
    gender = (gender or "").strip()
    height_group = (height_group or "").strip()
    birth_group = (birth_group or "").strip()
    status_filter = (status_filter or "").strip()

    if q:
        wheres.append("name LIKE ?")
        params.append(f"%{q}%")

    if m:
        wheres.append("manager_name LIKE ?")
        params.append(f"%{m}%")

    if gender:
        wheres.append("gender = ?")
        params.append(gender)

    if teacher_user_id is not None:
        wheres.append("teacher_user_id = ?")
        params.append(teacher_user_id)

    if height_group == "150":
        wheres.append("height_cm >= ? AND height_cm < ?")
        params.extend([150, 160])
    elif height_group == "160":
        wheres.append("height_cm >= ? AND height_cm < ?")
        params.extend([160, 170])
    elif height_group == "170":
        wheres.append("height_cm >= ? AND height_cm < ?")
        params.extend([170, 180])
    elif height_group == "180":
        wheres.append("height_cm >= ? AND height_cm < ?")
        params.extend([180, 190])

    if birth_group == "1980":
        wheres.append("birth_year BETWEEN ? AND ?")
        params.extend([1980, 1989])
    elif birth_group == "1990":
        wheres.append("birth_year BETWEEN ? AND ?")
        params.extend([1990, 1999])
    elif birth_group == "2000":
        wheres.append("birth_year BETWEEN ? AND ?")
        params.extend([2000, 2009])
    elif birth_group == "2010":
        wheres.append("birth_year BETWEEN ? AND ?")
        params.extend([2010, 2019])

    if status_filter == "active":
        wheres.append("""
            (
                contract_end_date IS NULL
                OR contract_end_date = ''
                OR date(contract_end_date) >= date('now','localtime')
            )
        """)
    elif status_filter == "expired":
        wheres.append("""
            contract_end_date IS NOT NULL
            AND contract_end_date != ''
            AND date(contract_end_date) < date('now','localtime')
        """)

    return wheres, params


def build_actor_order_by(sort: str = "") -> str:
    sort = (sort or "").strip()

    if sort == "youngest":
        return "ORDER BY birth_year DESC, id DESC"
    elif sort == "oldest":
        return "ORDER BY birth_year ASC, id DESC"
    elif sort == "new_contract":
        return """
        ORDER BY
            CASE WHEN contract_date IS NULL OR contract_date = '' THEN 1 ELSE 0 END,
            contract_date DESC,
            id DESC
        """
    elif sort == "old_contract":
        return """
        ORDER BY
            CASE WHEN contract_date IS NULL OR contract_date = '' THEN 1 ELSE 0 END,
            contract_date ASC,
            id DESC
        """
    return "ORDER BY id DESC"

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

async def get_teacher_visible_actors_page(
    teacher_user_id: int,
    q: str = "",
    m: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    sort: str = "",
    status_filter: str = "",
    lesson_id: str = "",
    page: int = 1,
    per_page: int = 24,
):
    wheres = []
    params = []

    q = (q or "").strip()
    m = (m or "").strip()
    gender = (gender or "").strip()
    height_group = (height_group or "").strip()
    birth_group = (birth_group or "").strip()
    sort = (sort or "").strip()
    status_filter = (status_filter or "").strip()
    lesson_id = (lesson_id or "").strip()

    base_sql = """
        FROM actors a
        WHERE (
            a.teacher_user_id = ?
            OR a.id IN (
                SELECT la.actor_id
                FROM lesson_actor_assignments la
                JOIN teacher_lessons tl
                  ON tl.id = la.lesson_id
                WHERE tl.teacher_user_id = ?
            )
        )
    """
    params.extend([teacher_user_id, teacher_user_id])

    # ✅ 수업 필터
    if lesson_id:
        wheres.append("""
            a.id IN (
                SELECT la.actor_id
                FROM lesson_actor_assignments la
                JOIN teacher_lessons tl
                  ON tl.id = la.lesson_id
                WHERE tl.teacher_user_id = ?
                  AND la.lesson_id = ?
            )
        """)
        params.extend([teacher_user_id, int(lesson_id)])

    if q:
        wheres.append("a.name LIKE ?")
        params.append(f"%{q}%")

    if m:
        wheres.append("a.manager_name LIKE ?")
        params.append(f"%{m}%")

    if gender:
        wheres.append("a.gender = ?")
        params.append(gender)

    if height_group == "150":
        wheres.append("a.height_cm >= ? AND a.height_cm < ?")
        params.extend([150, 160])
    elif height_group == "160":
        wheres.append("a.height_cm >= ? AND a.height_cm < ?")
        params.extend([160, 170])
    elif height_group == "170":
        wheres.append("a.height_cm >= ? AND a.height_cm < ?")
        params.extend([170, 180])
    elif height_group == "180":
        wheres.append("a.height_cm >= ? AND a.height_cm < ?")
        params.extend([180, 190])

    if birth_group == "1980":
        wheres.append("a.birth_year BETWEEN ? AND ?")
        params.extend([1980, 1989])
    elif birth_group == "1990":
        wheres.append("a.birth_year BETWEEN ? AND ?")
        params.extend([1990, 1999])
    elif birth_group == "2000":
        wheres.append("a.birth_year BETWEEN ? AND ?")
        params.extend([2000, 2009])
    elif birth_group == "2010":
        wheres.append("a.birth_year BETWEEN ? AND ?")
        params.extend([2010, 2019])

    if status_filter == "active":
        wheres.append("""
            (
                a.contract_end_date IS NULL
                OR a.contract_end_date = ''
                OR date(a.contract_end_date) >= date('now','localtime')
            )
        """)
    elif status_filter == "expired":
        wheres.append("""
            a.contract_end_date IS NOT NULL
            AND a.contract_end_date != ''
            AND date(a.contract_end_date) < date('now','localtime')
        """)

    extra_where = ""
    if wheres:
        extra_where = " AND " + " AND ".join(wheres)

    if sort == "youngest":
        order_by = "ORDER BY a.birth_year DESC, a.id DESC"
    elif sort == "oldest":
        order_by = "ORDER BY a.birth_year ASC, a.id DESC"
    elif sort == "new_contract":
        order_by = """
        ORDER BY
            CASE WHEN a.contract_date IS NULL OR a.contract_date = '' THEN 1 ELSE 0 END,
            a.contract_date DESC,
            a.id DESC
        """
    elif sort == "old_contract":
        order_by = """
        ORDER BY
            CASE WHEN a.contract_date IS NULL OR a.contract_date = '' THEN 1 ELSE 0 END,
            a.contract_date ASC,
            a.id DESC
        """
    else:
        order_by = "ORDER BY a.id DESC"

    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        count_sql = f"SELECT COUNT(DISTINCT a.id) {base_sql} {extra_where}"
        cur = await db.execute(count_sql, params)
        total_count = (await cur.fetchone())[0]

        list_sql = f"""
            SELECT DISTINCT a.*
            {base_sql}
            {extra_where}
            {order_by}
            LIMIT ? OFFSET ?
        """
        cur = await db.execute(list_sql, params + [per_page, offset])
        actors = await cur.fetchall()

    return actors, total_count

async def get_filtered_actors_page(
    q: str = "",
    m: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    sort: str = "",
    status_filter: str = "",
    teacher_user_id: int | None = None,
    page: int = 1,
    per_page: int = 24,
):
    wheres, params = await build_actor_filters(
        q=q,
        m=m,
        gender=gender,
        height_group=height_group,
        birth_group=birth_group,
        status_filter=status_filter,
        teacher_user_id=teacher_user_id,
    )

    base_where = ""
    if wheres:
        base_where = " WHERE " + " AND ".join(wheres)

    order_by = build_actor_order_by(sort)
    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        count_sql = f"SELECT COUNT(*) FROM actors {base_where}"
        cur = await db.execute(count_sql, params)
        total_count = (await cur.fetchone())[0]

        list_sql = f"""
        SELECT * FROM actors
        {base_where}
        {order_by}
        LIMIT ? OFFSET ?
        """
        cur = await db.execute(list_sql, params + [per_page, offset])
        actors = await cur.fetchall()

    return actors, total_count

async def get_filtered_actors(
    q: str = "",
    m: str = "",
    ai_query: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    sort: str = "",
    status_filter: str = "",
    teacher_user_id: int | None = None,
):
    wheres, params = await build_actor_filters(
        q=q,
        m=m,
        gender=gender,
        height_group=height_group,
        birth_group=birth_group,
        status_filter=status_filter,
        teacher_user_id=teacher_user_id,
    )

    base_where = ""
    if wheres:
        base_where = " WHERE " + " AND ".join(wheres)

    order_by = build_actor_order_by(sort)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = f"""
        SELECT * FROM actors
        {base_where}
        {order_by}
        """
        cur = await db.execute(sql, params)
        actors = await cur.fetchall()

    ai_parsed = None
    ai_scored_results = None

    if ai_query:
        ai_scored_results, ai_parsed = apply_ai_search(actors, ai_query)
        actors = [item[0] for item in ai_scored_results]

    return actors, ai_parsed, ai_scored_results


@app.get("/")
async def index(
    request: Request,
    q: str | None = None,
    m: str | None = None,
    ai_query: str | None = None,
    gender: str | None = None,
    height_group: str | None = None,
    birth_group: str | None = None,
    sort: str | None = None,
    view: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=200),
    status_filter: str | None = None,
    lesson_id: str | None = None,
):
    current_user = await get_current_user(request)

    teacher_user_id = None
    if current_user and current_user["role"] == "teacher":
        teacher_user_id = current_user["id"]

    q = (q or "").strip()
    m = (m or "").strip()
    ai_query = (ai_query or "").strip()
    gender = (gender or "").strip()
    height_group = (height_group or "").strip()
    birth_group = (birth_group or "").strip()
    sort = (sort or "").strip()
    view = (view or "card").strip().lower()
    status_filter = (status_filter or "").strip()
    lesson_id = (lesson_id or "").strip()
    teacher_lessons = []

    if view not in ["card", "list"]:
        view = "card"

    ai_parsed = None
    ai_scored_results = None

    if ai_query:
        actors, ai_parsed, ai_scored_results = await get_filtered_actors(
            q=q,
            m=m,
            ai_query=ai_query,
            gender=gender,
            height_group=height_group,
            birth_group=birth_group,
            sort=sort,
            status_filter=status_filter,
            teacher_user_id=teacher_user_id,
        )

        total_count = len(actors)
        total_pages = max(1, math.ceil(total_count / per_page))

        if page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        actors_page = actors[start_idx:end_idx]

    else:
        if teacher_user_id is not None:
            teacher_lessons = await get_teacher_lessons(teacher_user_id)

            actors_page, total_count = await get_teacher_visible_actors_page(
                teacher_user_id=teacher_user_id,
                q=q,
                m=m,
                gender=gender,
                height_group=height_group,
                birth_group=birth_group,
                sort=sort,
                status_filter=status_filter,
                lesson_id=lesson_id,
                page=page,
                per_page=per_page,
            )
        else:
            actors_page, total_count = await get_filtered_actors_page(
                q=q,
                m=m,
                gender=gender,
                height_group=height_group,
                birth_group=birth_group,
                sort=sort,
                status_filter=status_filter,
                teacher_user_id=teacher_user_id,
                page=page,
                per_page=per_page,
            )

        total_pages = max(1, math.ceil(total_count / per_page))

    today_str = datetime.now().strftime("%Y-%m-%d")

    actors_page = [dict(actor) for actor in actors_page]

    for actor in actors_page:
        end_date = (actor.get("contract_end_date") or "").strip()

        if not end_date:
            actor["contract_status"] = "active"
            actor["contract_status_label"] = "활동중"
        elif end_date < today_str:
            actor["contract_status"] = "expired"
            actor["contract_status_label"] = "계약만료"
        else:
            actor["contract_status"] = "active"
            actor["contract_status_label"] = "활동중"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "actors": actors_page,
            "q": q,
            "m": m,
            "ai_query": ai_query,
            "ai_parsed": ai_parsed,
            "ai_scored_results": ai_scored_results,
            "gender": gender,
            "height_group": height_group,
            "birth_group": birth_group,
            "sort": sort,
            "status_filter": status_filter,
            "view": view,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_count": total_count,
            "current_user": current_user,
            "lesson_id": lesson_id,
            "teacher_lessons": teacher_lessons,
        }
    )

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
@app.get("/actors/new", response_class=HTMLResponse)
async def actor_new_page(request: Request):
    current_user = await require_login_user(request)
    if not can_create_actor(current_user):
        raise HTTPException(status_code=403, detail="배우 등록 권한이 없습니다.")

    teacher_users = await get_teacher_users()

    return templates.TemplateResponse(
        "actor_new.html",
        {
            "request": request,
            "current_user": current_user,
            "teacher_users": teacher_users,
        }
    )


# ✅ 핵심: tab 쿼리로 탭 유지 (앵커 제거)
@app.get("/actors/{actor_id}")
async def actor_detail(
    request: Request,
    actor_id: int,
    tab: str = Query("compcard"),
    q: str = "",
    m: str = "",
    ai_query: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    sort: str = "",
    view: str = "card",
    page: int = 1,
    per_page: int = 24,
    status_filter: str = "",
    lesson_id: str = "",
):
    current_user = await get_current_user(request)

    if current_user and current_user["role"] == "teacher":
        allowed = await teacher_can_access_actor(current_user, actor_id)
        if not allowed:
            raise HTTPException(status_code=403, detail="담당 배우만 볼 수 있습니다.")
        if tab != "classlog":
            tab = "classlog"


    class_logs = []
    auditions = []
    acting_videos = []
    casting_management_logs = []
    casting_meetings = []
    first_meetings = []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
            SELECT
                a.*,
                u.display_name AS teacher_user_name
            FROM actors a
            LEFT JOIN users u
            ON a.teacher_user_id = u.id
            WHERE a.id = ?
        """, (actor_id,))
        actor = await cur.fetchone()
        if not actor:
            return RedirectResponse("/", status_code=302)

        actor = dict(actor)

        today_str = datetime.now().strftime("%Y-%m-%d")
        end_date = (actor.get("contract_end_date") or "").strip()

        if not end_date:
            actor["contract_status"] = "active"
            actor["contract_status_label"] = "활동중"
        elif end_date < today_str:
            actor["contract_status"] = "expired"
            actor["contract_status_label"] = "계약만료"
        else:
            actor["contract_status"] = "active"
            actor["contract_status_label"] = "활동중"

        current_tab = (tab or "compcard").strip()

        if current_tab == "classlog":
            cur = await db.execute(
                "SELECT * FROM class_logs WHERE actor_id=? ORDER BY meet_date DESC, id DESC",
                (actor_id,)
            )
            class_logs = await cur.fetchall()

        elif current_tab == "auditions":
            cur = await db.execute(
                "SELECT * FROM auditions WHERE actor_id=? ORDER BY aud_date DESC, id DESC",
                (actor_id,)
            )
            auditions = await cur.fetchall()

        elif current_tab == "video":
            cur = await db.execute(
                "SELECT * FROM acting_videos WHERE actor_id=? ORDER BY created_at DESC, id DESC",
                (actor_id,)
            )
            acting_videos = await cur.fetchall()

        elif current_tab == "casting_management":
            cur = await db.execute("""
                SELECT * FROM casting_management_logs
                WHERE actor_id=?
                ORDER BY meet_date DESC, id DESC
            """, (actor_id,))
            casting_management_logs = await cur.fetchall()

        elif current_tab == "casting_meetings":
            cur = await db.execute("""
                SELECT * FROM casting_meetings
                WHERE actor_id=?
                ORDER BY meet_date DESC, id DESC
            """, (actor_id,))
            casting_meetings = await cur.fetchall()

        elif current_tab == "first_meeting":
            cur = await db.execute("""
                SELECT * FROM first_meetings
                WHERE actor_id=?
                ORDER BY meet_date DESC, id DESC
            """, (actor_id,))
            first_meetings = await cur.fetchall()

    return templates.TemplateResponse(
        "actor_detail.html",
        {
            "request": request,
            "actor": actor,
            "tab": tab,
            "class_logs": class_logs,
            "auditions": auditions,
            "acting_videos": acting_videos,
            "casting_management_logs": casting_management_logs,
            "casting_meetings": casting_meetings,
            "first_meetings": first_meetings,
            "q": q,
            "m": m,
            "ai_query": ai_query,
            "gender": gender,
            "height_group": height_group,
            "birth_group": birth_group,
            "sort": sort,
            "view": view,
            "page": page,
            "per_page": per_page,
            "status_filter": status_filter,
            "lesson_id": lesson_id,
            "current_user": current_user,
        }
    )

@app.get("/actors/{actor_id}/edit", response_class=HTMLResponse)
async def actor_edit_page(
    request: Request,
    actor_id: int,
    q: str = "",
    m: str = "",
    ai_query: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    sort: str = "",
    view: str = "card",
    page: int = 1,
    per_page: int = 20,
    status_filter: str = "",
):
    current_user = await require_admin_or_staff(request)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM actors WHERE id = ?", (actor_id,))
        actor = await cur.fetchone()

    if not actor:
        raise HTTPException(status_code=404, detail="배우를 찾을 수 없습니다.")

    teacher_users = await get_teacher_users()

    return templates.TemplateResponse(
        "actor_edit.html",
        {
            "request": request,
            "current_user": current_user,
            "actor": dict(actor),
            "teacher_users": teacher_users,
            "q": q,
            "m": m,
            "ai_query": ai_query,
            "gender": gender,
            "height_group": height_group,
            "birth_group": birth_group,
            "sort": sort,
            "view": view,
            "page": page,
            "per_page": per_page,
            "status_filter": status_filter,
        }
    )

@app.post("/actors/new")
async def actor_new(
    request: Request,
    name: str = Form(...),
    manager_name: str = Form(""),
    gender: str = Form(""),
    birth_year: str = Form(""),
    height_cm: str = Form(""),
    weight_kg: str = Form(""),
    school: str = Form(""),
    hobby: str = Form(""),
    specialty: str = Form(""),
    contract_date: str = Form(""),
    contract_end_date: str = Form(""),
    bio: str = Form(""),
    teacher_user_id: str = Form(""),
    phone_last4: str = Form(""),
    photo: UploadFile | None = File(None),
    compcard: UploadFile | None = File(None),
    acting_videos: list[UploadFile] | UploadFile | None = File(None),
):
    current_user = await require_login_user(request)
    if not can_create_actor(current_user):
        raise HTTPException(status_code=403, detail="배우 등록 권한이 없습니다.")

    name = (name or "").strip()
    manager_name = (manager_name or "").strip()
    gender = (gender or "").strip()
    school = (school or "").strip()
    hobby = (hobby or "").strip()
    specialty = (specialty or "").strip()
    bio = (bio or "").strip()

    birth_year_clean = clean_birth_year(birth_year)
    contract_date_clean = clean_date(contract_date)
    contract_end_date_clean = clean_date(contract_end_date)

    if contract_date_clean and not contract_end_date_clean:
        try:
            start_date = datetime.strptime(contract_date_clean, "%Y-%m-%d")
            next_year = start_date.replace(year=start_date.year + 1)
            contract_end_date_clean = (next_year - timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            contract_end_date_clean = None

    try:
        height_cm_value = float(height_cm) if str(height_cm).strip() else None
    except Exception:
        height_cm_value = None

    try:
        weight_kg_value = float(weight_kg) if str(weight_kg).strip() else None
    except Exception:
        weight_kg_value = None

    phone_last4 = "".join(ch for ch in (phone_last4 or "").strip() if ch.isdigit())[:4]

    teacher_user_id_value = None
    if str(teacher_user_id).strip():
        try:
            teacher_user_id_value = int(str(teacher_user_id).strip())
        except Exception:
            teacher_user_id_value = None

    photo_path = None
    photo_thumb_path = None
    if photo and photo.filename:
        photo_path = save_upload(photo, "photo")
        photo_thumb_path = make_thumbnail_from_url(photo_path, "photo_thumb")

    compcard_path = None
    compcard_preview_path = None
    if compcard and compcard.filename:
        compcard_path = save_upload(compcard, "compcard")

        ext = os.path.splitext(compcard.filename or "")[1].lower()
        if ext == ".pdf":
            compcard_preview_path = compcard_path
        elif ext in [".ppt", ".pptx"]:
            compcard_preview_path = _make_ppt_first_slide_preview(compcard_path)
        elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
            compcard_preview_path = compcard_path

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO actors (
                name, birth_year, height_cm, weight_kg, photo_path, photo_thumb_path, bio,
                school, hobby, specialty, contract_date, contract_end_date,
                manager_name, gender, compcard_path, compcard_preview_path, teacher_user_id, phone_last4
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            birth_year_clean,
            height_cm_value,
            weight_kg_value,
            photo_path,
            photo_thumb_path,
            bio,
            school,
            hobby,
            specialty,
            contract_date_clean,
            contract_end_date_clean,
            manager_name,
            gender,
            compcard_path,
            compcard_preview_path,
            teacher_user_id_value,
            phone_last4,
        ))
        await db.commit()

        actor_id = cur.lastrowid

        video_files = normalize_uploadfiles(acting_videos)
        now = datetime.now().isoformat(timespec="seconds")

        for video in video_files:
            if video and video.filename:
                video_path = save_upload(video, "acting_video")
                await db.execute("""
                    INSERT INTO acting_videos (actor_id, video_path, original_name, created_at)
                    VALUES (?, ?, ?, ?)
                """, (actor_id, video_path, video.filename, now))

        await db.commit()

    return RedirectResponse(url=f"/actors/{actor_id}", status_code=303)

@app.post("/actors/{actor_id}/edit")
async def actor_edit(
    request: Request,
    actor_id: int,
    name: str = Form(...),
    manager_name: str = Form(""),
    gender: str = Form(""),
    birth_year: str = Form(""),
    height_cm: str = Form(""),
    weight_kg: str = Form(""),
    school: str = Form(""),
    hobby: str = Form(""),
    specialty: str = Form(""),
    contract_date: str = Form(""),
    contract_end_date: str = Form(""),
    bio: str = Form(""),
    teacher_user_id: str = Form(""),
    phone_last4: str = Form(""),
    q: str = Form(""),
    m: str = Form(""),
    ai_query: str = Form(""),
    gender_filter: str = Form(""),
    height_group: str = Form(""),
    birth_group: str = Form(""),
    sort: str = Form(""),
    view: str = Form("card"),
    page: int = Form(1),
    per_page: int = Form(20),
    status_filter: str = Form(""),
    lesson_id: str = Form(""),
    photo: UploadFile | None = File(None),
    compcard: UploadFile | None = File(None),
    acting_videos: list[UploadFile] | UploadFile | None = File(None),
):
    current_user = await require_admin_or_staff(request)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM actors WHERE id = ?", (actor_id,))
        actor = await cur.fetchone()

    if not actor:
        raise HTTPException(status_code=404, detail="배우를 찾을 수 없습니다.")

    actor = dict(actor)

    name = (name or "").strip()
    manager_name = (manager_name or "").strip()
    gender = (gender or "").strip()
    school = (school or "").strip()
    hobby = (hobby or "").strip()
    specialty = (specialty or "").strip()
    bio = (bio or "").strip()

    birth_year_clean = clean_birth_year(birth_year)
    contract_date_clean = clean_date(contract_date)
    contract_end_date_clean = clean_date(contract_end_date)

    if contract_date_clean and not contract_end_date_clean:
        try:
            start_date = datetime.strptime(contract_date_clean, "%Y-%m-%d")
            next_year = start_date.replace(year=start_date.year + 1)
            contract_end_date_clean = (next_year - timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            contract_end_date_clean = None

    try:
        height_cm_value = float(height_cm) if str(height_cm).strip() else None
    except Exception:
        height_cm_value = None

    try:
        weight_kg_value = float(weight_kg) if str(weight_kg).strip() else None
    except Exception:
        weight_kg_value = None

    phone_last4_clean = "".join(ch for ch in (phone_last4 or "").strip() if ch.isdigit())[:4]
    if not phone_last4_clean:
        phone_last4_clean = "".join(ch for ch in (actor.get("phone_last4") or "").strip() if ch.isdigit())[:4]
    phone_last4 = phone_last4_clean

    teacher_user_id_value = None
    if str(teacher_user_id).strip():
        try:
            teacher_user_id_value = int(str(teacher_user_id).strip())
        except Exception:
            teacher_user_id_value = None

    photo_path = actor.get("photo_path")
    photo_thumb_path = actor.get("photo_thumb_path")
    if photo and photo.filename:
        try_remove_by_url(actor.get("photo_path"))
        try_remove_by_url(actor.get("photo_thumb_path"))
        photo_path = save_upload(photo, "photo")
        photo_thumb_path = make_thumbnail_from_url(photo_path, "photo_thumb")

    compcard_path = actor.get("compcard_path")
    compcard_preview_path = actor.get("compcard_preview_path")
    if compcard and compcard.filename:
        try_remove_by_url(actor.get("compcard_path"))
        if actor.get("compcard_preview_path") and actor.get("compcard_preview_path") != actor.get("compcard_path"):
            try_remove_by_url(actor.get("compcard_preview_path"))

        compcard_path = save_upload(compcard, "compcard")
        ext = os.path.splitext(compcard.filename or "")[1].lower()

        if ext == ".pdf":
            compcard_preview_path = compcard_path
        elif ext in [".ppt", ".pptx"]:
            compcard_preview_path = _make_ppt_first_slide_preview(compcard_path)
        elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
            compcard_preview_path = compcard_path
        else:
            compcard_preview_path = None

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE actors
            SET
                name = ?,
                birth_year = ?,
                height_cm = ?,
                weight_kg = ?,
                photo_path = ?,
                photo_thumb_path = ?,
                bio = ?,
                school = ?,
                hobby = ?,
                specialty = ?,
                contract_date = ?,
                contract_end_date = ?,
                manager_name = ?,
                gender = ?,
                compcard_path = ?,
                compcard_preview_path = ?,
                teacher_user_id = ?,
                phone_last4 = ?
            WHERE id = ?
        """, (
            name,
            birth_year_clean,
            height_cm_value,
            weight_kg_value,
            photo_path,
            photo_thumb_path,
            bio,
            school,
            hobby,
            specialty,
            contract_date_clean,
            contract_end_date_clean,
            manager_name,
            gender,
            compcard_path,
            compcard_preview_path,
            teacher_user_id_value,
            phone_last4,
            actor_id,
        ))

        video_files = normalize_uploadfiles(acting_videos)
        now = datetime.now().isoformat(timespec="seconds")

        for video in video_files:
            if video and video.filename:
                video_path = save_upload(video, "acting_video")
                await db.execute("""
                    INSERT INTO acting_videos (actor_id, video_path, original_name, created_at)
                    VALUES (?, ?, ?, ?)
                """, (actor_id, video_path, video.filename, now))

        await db.commit()

    redirect_url = (
        f"/actors/{actor_id}"
        f"?q={quote(q or '')}"
        f"&m={quote(m or '')}"
        f"&ai_query={quote(ai_query or '')}"
        f"&gender={quote(gender_filter or '')}"
        f"&height_group={quote(height_group or '')}"
        f"&birth_group={quote(birth_group or '')}"
        f"&sort={quote(sort or '')}"
        f"&view={quote(view or 'card')}"
        f"&page={page or 1}"
        f"&per_page={per_page or 20}"
        f"&status_filter={quote(status_filter or '')}"
        f"&lesson_id={quote(lesson_id or '')}"
    )
    return RedirectResponse(url=redirect_url, status_code=303)

@app.post("/actors/{actor_id}/delete")
async def actor_delete(request: Request, actor_id: int):
    current_user = await require_actor_edit_permission(request, actor_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("""
        SELECT photo_path, compcard_path, compcard_preview_path, acting_video_path
        FROM actors WHERE id=?
        """, (actor_id,))
        actor_row = await cur.fetchone()

        cur = await db.execute("SELECT video_path FROM acting_videos WHERE actor_id=?", (actor_id,))
        video_rows = await cur.fetchall()

        await db.execute("DELETE FROM actors WHERE id=?", (actor_id,))
        await db.commit()

    if actor_row:
        try_remove_by_url(actor_row["photo_path"])
        try_remove_by_url(actor_row["compcard_path"])
        try_remove_by_url(actor_row["compcard_preview_path"])
        try_remove_by_url(actor_row["acting_video_path"])

    for vr in video_rows:
        try_remove_by_url(vr["video_path"])

    return RedirectResponse("/", status_code=303)


@app.post("/actors/{actor_id}/videos/{video_id}/delete")
async def delete_acting_video(request: Request, actor_id: int, video_id: int):
    current_user = await require_record_delete_permission(request, actor_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT video_path FROM acting_videos WHERE id=? AND actor_id=?",
            (video_id, actor_id)
        )
        row = await cur.fetchone()

        await db.execute("DELETE FROM acting_videos WHERE id=? AND actor_id=?", (video_id, actor_id))
        await db.commit()

    if row:
        try_remove_by_url(row["video_path"])

    # ✅ 앵커 삭제 -> tab=video
    return RedirectResponse(actor_url(actor_id, "video"), status_code=303)


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


async def get_teacher_users():
    async with open_db() as db:
        return await teachers_service.get_active_teachers(db)


async def get_teacher_lessons(teacher_user_id: int):
    async with open_db() as db:
        return await teachers_service.get_teacher_lessons(db, teacher_user_id)
