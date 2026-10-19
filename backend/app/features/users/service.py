import aiosqlite

from app.core.database import transaction
from app.core.errors import BadRequest, FormError, NotFound
from app.core.security import hash_password
from app.core.validators import now_str
from app.features.teachers import service as teachers_service
from app.features.users import repository

ROLES = ["admin", "staff", "teacher"]


async def _get_user_or_404(db: aiosqlite.Connection, user_id: int) -> dict:
    user = await repository.get_user(db, user_id)
    if not user:
        raise NotFound("계정을 찾을 수 없습니다.")
    return user


async def create_user(
    db: aiosqlite.Connection,
    username: str,
    password: str,
    password_confirm: str,
    display_name: str,
    role: str,
):
    username = (username or "").strip()
    password = (password or "").strip()
    password_confirm = (password_confirm or "").strip()
    display_name = (display_name or "").strip()
    role = (role or "").strip()

    if not username or not display_name or not password:
        raise FormError("아이디, 비밀번호, 이름은 필수입니다.")
    if len(username) < 4:
        raise FormError("아이디는 4자 이상으로 입력해주세요.")
    if len(password) < 4:
        raise FormError("비밀번호는 4자 이상으로 입력해주세요.")
    if password != password_confirm:
        raise FormError("비밀번호 확인이 일치하지 않습니다.")
    if role not in ROLES:
        raise FormError("권한 값이 올바르지 않습니다.")
    if await repository.username_exists(db, username):
        raise FormError("이미 사용 중인 아이디입니다.")

    async with transaction(db):
        new_user_id = await repository.insert_user(
            db, username, hash_password(password), display_name, role, now_str()
        )
        if role == "teacher":
            await teachers_service.ensure_profile(db, new_user_id)
    return new_user_id


async def list_users(db: aiosqlite.Connection) -> list[dict]:
    return await repository.list_users(db)


async def get_user(db: aiosqlite.Connection, user_id: int) -> dict:
    return await _get_user_or_404(db, user_id)


async def set_active(db: aiosqlite.Connection, current_user: dict, user_id: int, is_active: bool):
    target = await _get_user_or_404(db, user_id)

    if target["id"] == current_user["id"]:
        raise BadRequest("현재 로그인한 본인 계정은 비활성화할 수 없습니다.")

    async with transaction(db):
        await repository.set_active(db, user_id, 1 if is_active else 0)


async def change_role(db: aiosqlite.Connection, current_user: dict, user_id: int, role: str):
    role = (role or "").strip()
    if role not in ROLES:
        raise FormError("권한 값이 올바르지 않습니다.")

    target = await _get_user_or_404(db, user_id)

    if target["id"] == current_user["id"]:
        raise FormError("현재 로그인한 본인 계정의 권한은 변경할 수 없습니다.")

    # 마지막 admin 보호
    if target["role"] == "admin" and role != "admin":
        if await repository.count_admins(db) <= 1:
            raise FormError("마지막 관리자 계정의 권한은 변경할 수 없습니다.")

    async with transaction(db):
        await repository.set_role(db, user_id, role)
        if role == "teacher":
            await teachers_service.ensure_profile(db, user_id)


async def reset_password(db: aiosqlite.Connection, user_id: int, new_password: str, new_password_confirm: str) -> dict:
    """비밀번호를 바꾸고 대상 계정을 반환한다."""
    new_password = (new_password or "").strip()
    new_password_confirm = (new_password_confirm or "").strip()

    if len(new_password) < 4:
        raise FormError("비밀번호는 4자 이상으로 입력해주세요.")
    if new_password != new_password_confirm:
        raise FormError("비밀번호 확인이 일치하지 않습니다.")

    target = await _get_user_or_404(db, user_id)

    async with transaction(db):
        await repository.set_password_hash(db, user_id, hash_password(new_password))
    return target


async def delete_user(db: aiosqlite.Connection, current_user: dict, user_id: int):
    target = await _get_user_or_404(db, user_id)

    if target["id"] == current_user["id"]:
        raise BadRequest("현재 로그인한 본인 계정은 삭제할 수 없습니다.")

    if target["role"] == "admin" and await repository.count_admins(db) <= 1:
        raise BadRequest("마지막 관리자 계정은 삭제할 수 없습니다.")

    async with transaction(db):
        await repository.delete_user(db, user_id)


async def ensure_default_admin(db: aiosqlite.Connection):
    """admin 계정이 하나도 없으면 기본 관리자(admin / 1234)를 만든다."""
    if await repository.any_admin_exists(db):
        return

    async with transaction(db):
        await repository.insert_user(db, "admin", hash_password("1234"), "최고관리자", "admin", now_str())
    print("기본 관리자 계정 생성 완료: admin / 1234")
