"""
도메인 예외와 예외 핸들러.

service는 HTTP를 모르므로 HTTPException 대신 아래 예외를 발생시킨다.
핸들러가 상태 코드와 메시지를 응답으로 바꾼다.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

LOGIN_REQUIRED = "로그인이 필요합니다."


class AppError(Exception):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequest(AppError):
    status_code = 400


class Forbidden(AppError):
    status_code = 403


class NotFound(AppError):
    status_code = 404


class FormError(AppError):
    """사용자 입력 오류. router가 잡아서 같은 화면에 에러 메시지로 다시 보여준다."""
    status_code = 400


async def custom_http_exception_handler(request: Request, exc: HTTPException):
    accept = (request.headers.get("accept") or "").lower()

    # 로그인 필요 → 팝업만 띄우고 그대로 유지
    if exc.status_code == 403 and exc.detail == LOGIN_REQUIRED:
        if "text/html" in accept or "*/*" in accept:
            return HTMLResponse("""
<script>
  alert("로그인이 필요합니다.");
  history.back();
</script>
""", status_code=200)

    # 주의: 여기서 다시 raise 하면 500이 된다 (docs/found-issues.md #1)
    raise exc


async def app_error_handler(request: Request, exc: AppError):
    return await custom_http_exception_handler(
        request, HTTPException(status_code=exc.status_code, detail=exc.detail)
    )


def register_error_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, custom_http_exception_handler)
    app.add_exception_handler(AppError, app_error_handler)
