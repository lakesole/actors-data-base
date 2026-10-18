"""
키오스크 모드 미들웨어.

출석 키오스크 화면을 열면 세션에 kiosk_mode가 켜지고,
그 상태에서는 키오스크 관련 경로 외에는 키오스크 화면으로 되돌린다.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

# 이 경로로 들어오면 키오스크 모드를 끈다
RELEASE_PATHS = ["/", "/attendance", "/login", "/logout"]

# 키오스크 모드에서도 접근할 수 있는 경로
ALLOWED_PREFIXES = ["/static", "/login", "/logout", "/attendance/kiosk"]


async def kiosk_mode_guard(request: Request, call_next):
    path = request.url.path

    if path in RELEASE_PATHS:
        request.session["kiosk_mode"] = False

    if request.session.get("kiosk_mode", False):
        if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            return RedirectResponse(url="/attendance/kiosk", status_code=303)

    return await call_next(request)
