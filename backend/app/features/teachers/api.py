import aiosqlite
from fastapi import APIRouter, Depends, Response

from app.core.auth import require_admin, require_admin_or_staff
from app.core.database import get_db
from app.features.teachers import service
from app.features.teachers.schemas import (
    CreatedOut,
    LessonActorsIn,
    LessonIn,
    ProfileIn,
    TeacherChoiceOut,
    TeacherOut,
)

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


@router.get("", response_model=list[TeacherOut], dependencies=[Depends(require_admin)])
async def list_teachers(db: aiosqlite.Connection = Depends(get_db)):
    """선생님 관리 화면: 선생님별 수업과 배정 배우."""
    return await service.get_teacher_management_rows(db)


@router.get("/choices", response_model=list[TeacherChoiceOut], dependencies=[Depends(require_admin_or_staff)])
async def teacher_choices(db: aiosqlite.Connection = Depends(get_db)):
    """배우 등록/수정 화면의 담당 선생님 선택지 (활성 계정만)."""
    return await service.get_active_teachers(db)


@router.put("/{teacher_user_id}/profile", status_code=204, dependencies=[Depends(require_admin)])
async def save_profile(teacher_user_id: int, body: ProfileIn, db: aiosqlite.Connection = Depends(get_db)):
    await service.save_profile(db, teacher_user_id, body.lesson_subject, body.lesson_days)
    return Response(status_code=204)


@router.post("/{teacher_user_id}/lessons", response_model=CreatedOut, status_code=201, dependencies=[Depends(require_admin)])
async def add_lesson(teacher_user_id: int, body: LessonIn, db: aiosqlite.Connection = Depends(get_db)):
    lesson_id = await service.add_lesson(db, teacher_user_id, body.lesson_name, body.lesson_days)
    return {"id": lesson_id}


@router.delete("/lessons/{lesson_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_lesson(lesson_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await service.delete_lesson(db, lesson_id)
    return Response(status_code=204)


@router.put("/lessons/{lesson_id}/actors", status_code=204, dependencies=[Depends(require_admin)])
async def replace_lesson_actors(lesson_id: int, body: LessonActorsIn, db: aiosqlite.Connection = Depends(get_db)):
    await service.replace_lesson_actors(db, lesson_id, body.actor_ids)
    return Response(status_code=204)
