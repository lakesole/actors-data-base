import aiosqlite
from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import require_admin, require_login
from app.core.database import get_db
from app.features.attendance import service
from app.features.attendance.schemas import (
    AttendancePageOut,
    AttendanceSaveIn,
    KioskCheckIn,
    KioskCheckOut,
    KioskInfoOut,
)

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("", response_model=AttendancePageOut)
async def get_attendance(
    lesson_id: str = "",
    attendance_date: str = "",
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    """수업 목록과 선택한 수업의 출결. lesson_id를 비우면 첫 번째 수업, 날짜를 비우면 오늘."""
    return await service.get_page_data(db, user, lesson_id, attendance_date)


@router.put("", status_code=204)
async def save_attendance(
    body: AttendanceSaveIn,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    entries = {e.actor_id: e.model_dump() for e in body.entries}
    await service.save_attendance(db, user, body.lesson_id, body.attendance_date, entries)
    return Response(status_code=204)


@router.get("/kiosk", response_model=KioskInfoOut)
async def kiosk_info(
    request: Request,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    """키오스크 화면 정보. 호출하면 이 세션은 키오스크 모드가 된다."""
    request.session["kiosk_mode"] = True
    return await service.get_kiosk_page_data(db)


@router.post("/kiosk/check", response_model=KioskCheckOut)
async def kiosk_check(
    body: KioskCheckIn,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    return await service.kiosk_check(db, user, body.phone_last4)


@router.post("/kiosk/exit", status_code=204, dependencies=[Depends(require_admin)])
async def kiosk_exit(request: Request):
    request.session["kiosk_mode"] = False
    return Response(status_code=204)
