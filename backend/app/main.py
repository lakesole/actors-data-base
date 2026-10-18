"""
앱 생성과 라우터 등록만 한다. 기능 코드는 app/features/<기능>/ 아래에 있다.

실행: backend/ 에서  uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import (
    SECRET_KEY,
    SESSION_COOKIE_NAME,
    SESSION_HTTPS_ONLY,
    SESSION_MAX_AGE,
    STATIC_DIR,
)
from app.core.database import open_db
from app.core.errors import register_error_handlers
from app.core.files import ensure_dirs
from app.core.schema import init_db, migrate_legacy_log_tables
from app.features.actor_records.router import router as actor_records_router
from app.features.actors import service as actors_service
from app.features.actors.router import router as actors_router
from app.features.attendance.kiosk import kiosk_mode_guard
from app.features.attendance.router import router as attendance_router
from app.features.auth.router import router as auth_router
from app.features.compcards.router import router as compcards_router
from app.features.teachers.router import router as teachers_router
from app.features.users import service as users_service
from app.features.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    await init_db()
    await migrate_legacy_log_tables()
    async with open_db() as db:
        await actors_service.normalize_actor_data(db)
        await users_service.ensure_default_admin(db)
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
register_error_handlers(app)

# 미들웨어는 나중에 추가한 것이 바깥쪽에서 먼저 실행된다 (세션 → 키오스크 순서)
app.middleware("http")(kiosk_mode_guard)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(teachers_router)
app.include_router(actors_router)
app.include_router(actor_records_router)
app.include_router(attendance_router)
app.include_router(compcards_router)


@app.get("/where", response_class=PlainTextResponse)
def where():
    return "YOU ARE SEEING: main.py (actor_db)"
