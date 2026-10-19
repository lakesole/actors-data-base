"""
키오스크 모드 미들웨어.

출석 키오스크 화면을 열면 세션에 kiosk_mode가 켜지고,
그 상태에서는 키오스크 관련 API 외의 /api 요청을 403 {"code": "KIOSK_MODE"}로 막는다.
프론트엔드는 이 코드를 받으면 키오스크 화면으로 이동한다.
"""
from fastapi import Request

from app.core.errors import error_json

API_PREFIX = "/api/"

# 이 API를 GET으로 호출하면 키오스크 모드를 끈다 (목록/출석부 화면으로 나간 경우)
RELEASE_GET_PATHS = ["/api/actors", "/api/attendance"]
# 로그인/로그아웃도 키오스크 모드를 끈다
RELEASE_PATHS = ["/api/auth/login", "/api/auth/logout"]

# 키오스크 모드에서도 접근할 수 있는 API
API_ALLOWED_PREFIXES = ["/api/auth/", "/api/attendance/kiosk"]


async def kiosk_mode_guard(request: Request, call_next):
    path = request.url.path

    if path in RELEASE_PATHS or (request.method == "GET" and path in RELEASE_GET_PATHS):
        request.session["kiosk_mode"] = False

    if request.session.get("kiosk_mode", False) and path.startswith(API_PREFIX):
        if not any(path.startswith(prefix) for prefix in API_ALLOWED_PREFIXES):
            return error_json(403, "키오스크 모드에서는 사용할 수 없습니다.", "KIOSK_MODE")

    return await call_next(request)
