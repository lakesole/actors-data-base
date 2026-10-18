import aiosqlite

from app.core.database import transaction
from app.core.errors import Forbidden, FormError
from app.core.security import hash_password, verify_password
from app.features.auth import repository

LOGIN_FAILED = "아이디 또는 비밀번호가 올바르지 않습니다."


async def authenticate(db: aiosqlite.Connection, username: str, password: str) -> dict:
    user = await repository.find_by_username(db, (username or "").strip())

    if not user:
        raise FormError(LOGIN_FAILED)

    if not user["is_active"]:
        raise FormError("비활성화된 계정입니다.")

    if not verify_password(password, user["password_hash"]):
        raise FormError(LOGIN_FAILED)

    return user


async def change_password(
    db: aiosqlite.Connection,
    user: dict,
    current_password: str,
    new_password: str,
    new_password_confirm: str,
):
    current_password = (current_password or "").strip()
    new_password = (new_password or "").strip()
    new_password_confirm = (new_password_confirm or "").strip()

    password_hash = await repository.get_password_hash(db, user["id"])
    if password_hash is None:
        raise Forbidden("계정을 찾을 수 없습니다.")

    if not verify_password(current_password, password_hash):
        raise FormError("현재 비밀번호가 올바르지 않습니다.")

    if len(new_password) < 4:
        raise FormError("새 비밀번호는 4자 이상이어야 합니다.")

    if new_password != new_password_confirm:
        raise FormError("새 비밀번호 확인이 일치하지 않습니다.")

    async with transaction(db):
        await repository.update_password_hash(db, user["id"], hash_password(new_password))
