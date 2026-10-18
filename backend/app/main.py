import os
import uuid
from contextlib import asynccontextmanager
from copy import deepcopy

import aiosqlite
from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pptx import Presentation
from pypdf import PdfWriter
from starlette.middleware.sessions import SessionMiddleware

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
from app.features.attendance.kiosk import kiosk_mode_guard
from app.features.attendance.router import router as attendance_router
from app.features.actor_records.router import router as actor_records_router
from app.core.files import ensure_dirs, safe_download_filename, url_to_fs_path
from app.core.schema import init_db, migrate_legacy_log_tables
from app.features.actors import service as actors_service
from app.features.actors.router import router as actors_router
from app.features.auth.router import router as auth_router
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
app.include_router(attendance_router)
app.include_router(actor_records_router)
app.include_router(actors_router)
app.include_router(users_router)
app.include_router(teachers_router)
app.include_router(auth_router)


app.middleware("http")(kiosk_mode_guard)
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


# -------------------------
# 메인(검색 포함)
# -------------------------


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


# -------------------------
# 오디션 항목 CRUD
# -------------------------


# -------------------------
# 캐스팅관리 기록 항목 CRUD
# -------------------------


# -------------------------
# 캐스팅 미팅 기록 항목 CRUD
# -------------------------


# -------------------------
# 첫 미팅 기록 항목 CRUD
# -------------------------


# -------------------------
# Phase 3 전환용: 아직 main.py에 남은 라우트가 쓰는 다른 기능의 service
# -------------------------


async def get_filtered_actors(q="", m="", ai_query="", gender="", height_group="", birth_group="", sort="", status_filter=""):
    async with open_db() as db:
        f = actors_service.make_filters(q, m, gender, height_group, birth_group, sort, status_filter)
        return await actors_service.search_actors(db, f, (ai_query or "").strip())
