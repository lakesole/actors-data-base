"""
로그인 사용자 조회와 역할 기반 권한 검사.

router에서 Depends로 쓴다:
    user = Depends(require_login)
    user = Depends(require_admin)
"""
import aiosqlite
from fastapi import Depends, Request

from app.core.database import get_db
from app.core.errors import LOGIN_REQUIRED, Forbidden, Unauthorized


async def current_user(request: Request, db: aiosqlite.Connection = Depends(get_db)) -> dict | None:
    """로그인하지 않았거나 비활성 계정이면 None. 비활성 계정은 세션을 지운다."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    cur = await db.execute("""
        SELECT id, username, display_name, role, is_active
        FROM users
        WHERE id = ?
    """, (user_id,))
    user = await cur.fetchone()

    if not user or not user["is_active"]:
        request.session.clear()
        return None

    return dict(user)


async def require_login(user: dict | None = Depends(current_user)) -> dict:
    if not user:
        raise Unauthorized(LOGIN_REQUIRED)
    return user


async def require_admin(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin":
        raise Forbidden("관리자 권한이 필요합니다.")
    return user


async def require_admin_or_staff(user: dict = Depends(require_login)) -> dict:
    if user["role"] not in ["admin", "staff"]:
        raise Forbidden("관리자 또는 스태프 권한이 필요합니다.")
    return user

