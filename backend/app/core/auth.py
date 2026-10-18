"""로그인 사용자 조회와 역할 기반 권한 검사."""
from fastapi import HTTPException, Request

from app.core.database import open_db
from app.core.errors import LOGIN_REQUIRED


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


async def require_admin(request: Request):
    user = await require_login_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user


async def require_admin_or_staff(request: Request):
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
