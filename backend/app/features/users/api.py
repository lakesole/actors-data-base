import aiosqlite
from fastapi import APIRouter, Depends, Response

from app.core.auth import require_admin
from app.core.database import get_db
from app.features.users import service
from app.features.users.schemas import PasswordResetIn, UserCreateIn, UserOut, UserUpdateIn

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_admin)])
async def list_users(db: aiosqlite.Connection = Depends(get_db)):
    return await service.list_users(db)


@router.post("", response_model=UserOut, status_code=201, dependencies=[Depends(require_admin)])
async def create_user(body: UserCreateIn, db: aiosqlite.Connection = Depends(get_db)):
    user_id = await service.create_user(
        db, body.username, body.password, body.password_confirm, body.display_name, body.role
    )
    return await service.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdateIn,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    if body.role is not None:
        await service.change_role(db, user, user_id, body.role)
    if body.is_active is not None:
        await service.set_active(db, user, user_id, body.is_active)
    return await service.get_user(db, user_id)


@router.post("/{user_id}/reset-password", status_code=204, dependencies=[Depends(require_admin)])
async def reset_password(user_id: int, body: PasswordResetIn, db: aiosqlite.Connection = Depends(get_db)):
    await service.reset_password(db, user_id, body.new_password, body.new_password_confirm)
    return Response(status_code=204)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    user: dict = Depends(require_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.delete_user(db, user, user_id)
    return Response(status_code=204)
