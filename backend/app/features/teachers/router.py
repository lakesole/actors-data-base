import aiosqlite
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.core.auth import require_admin
from app.core.database import get_db
from app.features.teachers import service

router = APIRouter(prefix="/admin/teachers", dependencies=[Depends(require_admin)])

SAVED_URL = "/admin/users?success=teacher_saved"


@router.post("/{teacher_user_id}/save")
async def save_profile(
    teacher_user_id: int,
    lesson_subject: str = Form(""),
    lesson_days: str = Form(""),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.save_profile(db, teacher_user_id, lesson_subject, lesson_days)
    return RedirectResponse(url=SAVED_URL, status_code=303)


@router.post("/{teacher_user_id}/lesson/add")
async def add_lesson(
    teacher_user_id: int,
    lesson_name: str = Form(...),
    lesson_days: str = Form(...),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.add_lesson(db, teacher_user_id, lesson_name, lesson_days)
    return RedirectResponse(url=SAVED_URL, status_code=303)


@router.post("/lesson/{lesson_id}/delete")
async def delete_lesson(lesson_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await service.delete_lesson(db, lesson_id)
    return RedirectResponse(url=SAVED_URL, status_code=303)


@router.post("/lesson/{lesson_id}/actors/save")
async def save_lesson_actors(request: Request, lesson_id: int, db: aiosqlite.Connection = Depends(get_db)):
    form = await request.form()
    await service.replace_lesson_actors(db, lesson_id, form.getlist("actor_ids"))
    return RedirectResponse(url=SAVED_URL, status_code=303)
