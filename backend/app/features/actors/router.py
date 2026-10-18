from urllib.parse import quote

import aiosqlite
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import current_user, require_admin_or_staff, require_login
from app.core.database import get_db
from app.core.templating import templates
from app.core.urls import actor_url
from app.features.actors import service
from app.features.actors.service import ActorForm

router = APIRouter()


def actor_form(
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
) -> ActorForm:
    return ActorForm(
        name=name, manager_name=manager_name, gender=gender, birth_year=birth_year,
        height_cm=height_cm, weight_kg=weight_kg, school=school, hobby=hobby,
        specialty=specialty, contract_date=contract_date, contract_end_date=contract_end_date,
        bio=bio, teacher_user_id=teacher_user_id, phone_last4=phone_last4,
    )


# ---------- 목록 ----------

@router.get("/")
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
    user: dict | None = Depends(current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    f = service.make_filters(q, m, gender, height_group, birth_group, sort, status_filter)
    ai_query = (ai_query or "").strip()
    lesson_id = (lesson_id or "").strip()
    view = (view or "card").strip().lower()
    if view not in ["card", "list"]:
        view = "card"

    data = await service.get_index_data(db, user, f, ai_query, lesson_id, page, per_page)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "q": f.q,
        "m": f.m,
        "ai_query": ai_query,
        "gender": f.gender,
        "height_group": f.height_group,
        "birth_group": f.birth_group,
        "sort": f.sort,
        "status_filter": f.status_filter,
        "view": view,
        "per_page": per_page,
        "current_user": user,
        "lesson_id": lesson_id,
        **data,
    })


# ---------- 등록 ----------

@router.get("/actors/new", response_class=HTMLResponse)
async def actor_new_page(
    request: Request,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    service.ensure_can_create(user)
    return templates.TemplateResponse("actor_new.html", {
        "request": request,
        "current_user": user,
        "teacher_users": await service.get_teacher_choices(db),
    })


# ---------- 상세 ----------

@router.get("/actors/{actor_id}")
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
    user: dict | None = Depends(current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    data = await service.get_detail_data(db, user, actor_id, tab)
    if data is None:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse("actor_detail.html", {
        "request": request,
        **data,
        # 목록으로 돌아갈 때 검색 조건을 유지하기 위한 값
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
        "current_user": user,
    })


# ---------- 수정 ----------

@router.get("/actors/{actor_id}/edit", response_class=HTMLResponse)
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
    user: dict = Depends(require_admin_or_staff),
    db: aiosqlite.Connection = Depends(get_db),
):
    actor = await service.get_actor_or_404(db, actor_id)

    return templates.TemplateResponse("actor_edit.html", {
        "request": request,
        "current_user": user,
        "actor": actor,
        "teacher_users": await service.get_teacher_choices(db),
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
    })


@router.post("/actors/new")
async def actor_new(
    form: ActorForm = Depends(actor_form),
    photo: UploadFile | None = File(None),
    compcard: UploadFile | None = File(None),
    # 주의: 유니온 타입이라 여러 파일 중 마지막 1개만 들어온다 (docs/found-issues.md #13)
    acting_videos: list[UploadFile] | UploadFile | None = File(None),
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    service.ensure_can_create(user)
    actor_id = await service.create_actor(db, form, photo, compcard, acting_videos)
    return RedirectResponse(url=f"/actors/{actor_id}", status_code=303)


@router.post("/actors/{actor_id}/edit")
async def actor_edit(
    actor_id: int,
    form: ActorForm = Depends(actor_form),
    # 수정 후 상세 화면으로 돌아갈 때 유지할 목록 검색 조건
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
    user: dict = Depends(require_admin_or_staff),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.update_actor(db, actor_id, form, photo, compcard, acting_videos)

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


# ---------- 삭제 ----------

@router.post("/actors/{actor_id}/delete")
async def actor_delete(
    actor_id: int,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.delete_actor(db, user, actor_id)
    return RedirectResponse("/", status_code=303)


@router.post("/actors/{actor_id}/videos/{video_id}/delete")
async def delete_acting_video(
    actor_id: int,
    video_id: int,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.delete_video(db, user, actor_id, video_id)
    return RedirectResponse(actor_url(actor_id, "video"), status_code=303)
