from urllib.parse import quote

import aiosqlite
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import require_admin
from app.core.database import get_db
from app.core.errors import FormError
from app.core.templating import templates
from app.features.users import service

router = APIRouter(prefix="/admin/users")


async def _render_page(request: Request, db: aiosqlite.Connection, user: dict, error: str = "", success: str = ""):
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "current_user": user,
        **await service.get_admin_page_data(db),
        "error": error,
        "success": success,
    })


@router.get("", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    return await _render_page(request, db, user, success=request.query_params.get("success", ""))


@router.post("/new", response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(...),
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        await service.create_user(db, username, password, password_confirm, display_name, role)
    except FormError as e:
        return await _render_page(request, db, user, error=e.detail)
    return RedirectResponse(url="/admin/users?success=created", status_code=303)


@router.post("/{user_id}/toggle-active")
async def toggle_active(
    user_id: int,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.toggle_active(db, user, user_id)
    return RedirectResponse(url="/admin/users?success=toggled", status_code=303)


@router.post("/{user_id}/change-role", response_class=HTMLResponse)
async def change_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        await service.change_role(db, user, user_id, role)
    except FormError as e:
        return await _render_page(request, db, user, error=e.detail)
    return RedirectResponse(url="/admin/users?success=role_changed", status_code=303)


@router.post("/{user_id}/reset-password", response_class=HTMLResponse)
async def reset_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        target = await service.reset_password(db, user_id, new_password, new_password_confirm)
    except FormError as e:
        return await _render_page(request, db, user, error=e.detail)
    return RedirectResponse(
        url=f"/admin/users?success=pw_reset_{quote(target['username'])}",
        status_code=303,
    )


@router.post("/{user_id}/delete")
async def delete_user(
    user_id: int,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.delete_user(db, user, user_id)
    return RedirectResponse(url="/admin/users?success=deleted", status_code=303)
