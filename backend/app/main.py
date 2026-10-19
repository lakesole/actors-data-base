"""
앱 생성과 라우터 등록만 한다. 기능 코드는 app/features/<기능>/ 아래에 있다.

실행: backend/ 에서  uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import (
    SECRET_KEY,
    SESSION_COOKIE_NAME,
    SESSION_HTTPS_ONLY,
    SESSION_MAX_AGE,
    UPLOAD_DIR,
)
from app.core.database import open_db
from app.core.errors import register_error_handlers
from app.core.files import ensure_dirs
from app.core.schema import init_db, migrate_legacy_log_tables
from app.features.actor_records.api import router as actor_records_api
from app.features.actors.api import router as actors_api
from app.features.actors import service as actors_service
from app.features.attendance.api import router as attendance_api
from app.features.attendance.kiosk import kiosk_mode_guard
from app.features.auth.api import router as auth_api
from app.features.compcards.api import router as compcards_api
from app.features.teachers.api import router as teachers_api
from app.features.users import service as users_service
from app.features.users.api import router as users_api


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
ensure_dirs()  # StaticFiles는 만들 때 폴더가 있어야 한다
# 업로드 파일만 공개한다. storage/ 전체를 마운트하면 DB 파일까지 노출된다.
app.mount("/media/uploads", StaticFiles(directory=UPLOAD_DIR), name="media")
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

# JSON API (/api/...). 화면은 frontend/가 담당한다.
app.include_router(auth_api)
app.include_router(users_api)
app.include_router(teachers_api)
app.include_router(actors_api)
app.include_router(actor_records_api)
app.include_router(attendance_api)
app.include_router(compcards_api)
