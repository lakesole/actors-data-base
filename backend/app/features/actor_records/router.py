"""
배우 기록 5종(수업일지, 오디션, 캐스팅 관리, 캐스팅 미팅, 첫 미팅)의 추가/수정/삭제 화면.

다섯 종류의 라우트 모양이 같아서 RECORD_TYPES마다 같은 라우트 5개를 등록한다.
    GET  /actors/{actor_id}/<path>/new
    POST /actors/{actor_id}/<path>/new
    GET  /actors/{actor_id}/<path>/{item_id}/edit
    POST /actors/{actor_id}/<path>/{item_id}/edit
    POST /actors/{actor_id}/<path>/{item_id}/delete
"""
import aiosqlite
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.core.auth import require_login
from app.core.database import get_db
from app.core.templating import templates
from app.core.urls import actor_url
from app.features.actor_records import service
from app.features.actor_records.service import RECORD_TYPES, RecordType

router = APIRouter()


def _register(t: RecordType):
    base = f"/actors/{{actor_id}}/{t.path}"

    def form_page(request: Request, actor_id: int, item: dict | None):
        return templates.TemplateResponse(t.template, {
            "request": request,
            "actor_id": actor_id,
            "mode": "edit" if item else "new",
            "item": item,
        })

    @router.get(f"{base}/new", name=f"{t.path}_new_page")
    async def new_page(
        request: Request,
        actor_id: int,
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        await service.ensure_can_edit(db, user, actor_id)
        return form_page(request, actor_id, None)

    @router.post(f"{base}/new", name=f"{t.path}_create")
    async def create(
        actor_id: int,
        # 날짜 필드 이름이 종류마다 달라서(meet_date / aud_date) alias로 받는다
        record_date: str = Form(..., alias=t.date_field),
        content: str = Form(...),
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        await service.create_record(db, user, t.path, actor_id, record_date, content)
        return RedirectResponse(actor_url(actor_id, t.tab), status_code=303)

    @router.get(f"{base}/{{item_id}}/edit", name=f"{t.path}_edit_page")
    async def edit_page(
        request: Request,
        actor_id: int,
        item_id: int,
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        await service.ensure_can_edit(db, user, actor_id)
        item = await service.get_record(db, t.path, actor_id, item_id)
        if not item:
            return RedirectResponse(actor_url(actor_id, t.tab), status_code=303)
        return form_page(request, actor_id, item)

    @router.post(f"{base}/{{item_id}}/edit", name=f"{t.path}_update")
    async def update(
        actor_id: int,
        item_id: int,
        record_date: str = Form(..., alias=t.date_field),
        content: str = Form(...),
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        await service.update_record(db, user, t.path, actor_id, item_id, record_date, content)
        return RedirectResponse(actor_url(actor_id, t.tab), status_code=303)

    @router.post(f"{base}/{{item_id}}/delete", name=f"{t.path}_delete")
    async def delete(
        actor_id: int,
        item_id: int,
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        await service.delete_record(db, user, t.path, actor_id, item_id)
        return RedirectResponse(actor_url(actor_id, t.tab), status_code=303)


for record_type in RECORD_TYPES.values():
    _register(record_type)
