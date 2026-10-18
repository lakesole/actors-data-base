"""
로그인 사용자 조회와 역할 기반 권한 검사.

router에서 Depends로 쓴다:
    user = Depends(require_login)
    user = Depends(require_admin)
"""
import aiosqlite
from fastapi import Depends, HTTPException, Request

from app.core.database import get_db, open_db
from app.core.errors import LOGIN_REQUIRED, Forbidden


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
        raise Forbidden(LOGIN_REQUIRED)
    return user


async def require_admin(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin":
        raise Forbidden("관리자 권한이 필요합니다.")
    return user


async def require_admin_or_staff(user: dict = Depends(require_login)) -> dict:
    if user["role"] not in ["admin", "staff"]:
        raise Forbidden("관리자 또는 스태프 권한이 필요합니다.")
    return user


# ---------------------------------------------------------------
# 아래는 main.py에 남아 있는 라우트용 (Phase 3에서 기능별로 옮기면서 제거)
# ---------------------------------------------------------------


async def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    async with open_db() as db:
        cur = await db.execute("""
            SELECT id, username, display_name, role, is_active
            FROM users
            WHERE id = ?
        """, (user_id,))
        user = await cur.fetchone()

    if not user:
        request.session.clear()
        return None

    if not user["is_active"]:
        request.session.clear()
        return None

    return dict(user)


def can_create_actor(user) -> bool:
    if not user:
        return False
    return user["role"] in ["admin", "staff"]


async def teacher_can_access_actor(user, actor_id: int) -> bool:
    if not user:
        return False

    if user["role"] in ["admin", "staff"]:
        return True

    if user["role"] != "teacher":
        return False

    async with open_db() as db:
        # 1) 기존 직접 배정도 허용
        cur = await db.execute("""
            SELECT id
            FROM actors
            WHERE id = ? AND teacher_user_id = ?
        """, (actor_id, user["id"]))
        row = await cur.fetchone()
        if row:
            return True

        # 2) 수업 배정 기반 허용
        cur = await db.execute("""
            SELECT la.id
            FROM lesson_actor_assignments la
            JOIN teacher_lessons tl
              ON tl.id = la.lesson_id
            WHERE la.actor_id = ?
              AND tl.teacher_user_id = ?
            LIMIT 1
        """, (actor_id, user["id"]))
        row = await cur.fetchone()

    return row is not None


async def require_login_user(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=403, detail=LOGIN_REQUIRED)
    return user


async def require_admin_legacy(request: Request):
    user = await require_login_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user


async def require_admin_or_staff_legacy(request: Request):
    user = await require_login_user(request)
    if user["role"] not in ["admin", "staff"]:
        raise HTTPException(status_code=403, detail="관리자 또는 스태프 권한이 필요합니다.")
    return user


async def require_actor_edit_permission(request: Request, actor_id: int):
    user = await require_login_user(request)

    if user["role"] in ["admin", "staff"]:
        return user

    if user["role"] == "teacher":
        allowed = await teacher_can_access_actor(user, actor_id)
        if not allowed:
            raise HTTPException(status_code=403, detail="담당 배우만 수정할 수 있습니다.")
        return user

    raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")


async def require_record_delete_permission(request: Request, actor_id: int):
    user = await require_login_user(request)

    if user["role"] in ["admin", "staff"]:
        return user

    raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")
