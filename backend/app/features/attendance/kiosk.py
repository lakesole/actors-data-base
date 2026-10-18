"""
키오스크 모드 미들웨어.

출석 키오스크 화면을 열면 세션에 kiosk_mode가 켜지고,
그 상태에서는 키오스크 관련 경로 외에는 막는다.
- 화면 요청: 키오스크 화면으로 303 이동
- API 요청: 403 {"code": "KIOSK_MODE"} → 프론트엔드가 키오스크 화면으로 이동
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.core.errors import error_json, is_api_request

# 이 경로로 들어오면 키오스크 모드를 끈다
RELEASE_PATHS = ["/", "/attendance", "/login", "/logout", "/api/auth/login", "/api/auth/logout"]

# 키오스크 모드에서도 접근할 수 있는 경로
ALLOWED_PREFIXES = ["/static", "/media", "/login", "/logout", "/attendance/kiosk"]
API_ALLOWED_PREFIXES = ["/api/auth/", "/api/attendance/kiosk"]


async def kiosk_mode_guard(request: Request, call_next):
    path = request.url.path

    if path in RELEASE_PATHS:
        request.session["kiosk_mode"] = False

    if request.session.get("kiosk_mode", False):
        if is_api_request(request):
            if not any(path.startswith(prefix) for prefix in API_ALLOWED_PREFIXES):
                return error_json(403, "키오스크 모드에서는 사용할 수 없습니다.", "KIOSK_MODE")
        elif not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            return RedirectResponse(url="/attendance/kiosk", status_code=303)

    return await call_next(request)
