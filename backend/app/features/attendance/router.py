from urllib.parse import quote

import aiosqlite
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import require_admin, require_login
from app.core.database import get_db
from app.core.templating import templates
from app.features.attendance import service

router = APIRouter(prefix="/attendance")


@router.get("", response_class=HTMLResponse)
async def attendance_page(
    request: Request,
    lesson_id: str | None = None,
    attendance_date: str | None = None,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    data = await service.get_page_data(db, user, lesson_id, attendance_date)
    return templates.TemplateResponse("attendance.html", {
        "request": request,
        "current_user": user,
        **data,
    })


@router.post("/save")
async def attendance_save(
    request: Request,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    form = await request.form()
    lesson_id, attendance_date = await service.save_attendance(db, user, dict(form))
    return RedirectResponse(
        url=f"/attendance?lesson_id={lesson_id}&attendance_date={quote(attendance_date)}",
        status_code=303,
    )


@router.get("/kiosk", response_class=HTMLResponse)
async def kiosk_page(
    request: Request,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    request.session["kiosk_mode"] = True
    return templates.TemplateResponse("attendance_kiosk.html", {
        "request": request,
        "current_user": user,
        **await service.get_kiosk_page_data(db),
    })


@router.post("/kiosk/check")
async def kiosk_check(
    phone_last4: str = Form(""),
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    return await service.kiosk_check(db, user, phone_last4)


@router.get("/kiosk/exit", dependencies=[Depends(require_admin)])
async def kiosk_exit(request: Request):
    request.session["kiosk_mode"] = False
    return RedirectResponse(url="/attendance", status_code=303)
