import aiosqlite
from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import require_login
from app.core.database import get_db
from app.core.errors import Forbidden
from app.features.auth import service
from app.features.auth.schemas import LoginIn, MeOut, PasswordChangeIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=MeOut)
async def login(body: LoginIn, request: Request, db: aiosqlite.Connection = Depends(get_db)):
    """실패하면 422 VALIDATION_FAILED (detail에 화면에 보여줄 메시지)."""
    user = await service.authenticate(db, body.username, body.password)
    request.session["user_id"] = user["id"]
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request):
    request.session.clear()
    return Response(status_code=204)


@router.get("/me", response_model=MeOut)
async def me(user: dict = Depends(require_login)):
    return user


@router.post("/password", status_code=204)
async def change_password(
    body: PasswordChangeIn,
    request: Request,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        await service.change_password(db, user, body.current_password, body.new_password, body.new_password_confirm)
    except Forbidden:
        request.session.clear()
        raise
    return Response(status_code=204)
