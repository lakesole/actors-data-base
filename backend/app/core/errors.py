"""
도메인 예외와 예외 핸들러.

service는 HTTP를 모르므로 HTTPException 대신 아래 예외를 발생시킨다.
- /api 요청: {"detail": 메시지, "code": 코드} JSON과 상태 코드로 응답한다.
- 화면(Jinja) 요청: 리팩터링 전 동작을 그대로 유지한다 (Phase 6에서 화면과 함께 제거).
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

LOGIN_REQUIRED = "로그인이 필요합니다."
API_PREFIX = "/api/"


class AppError(Exception):
    status_code = 500
    code = "ERROR"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequest(AppError):
    status_code = 400
    code = "BAD_REQUEST"


class Unauthorized(AppError):
    status_code = 401
    code = "LOGIN_REQUIRED"


class Forbidden(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"


class FormError(AppError):
    """사용자 입력 오류. 화면에서는 같은 페이지에 에러로 다시 보여주고, API에서는 422로 응답한다."""
    status_code = 422
    code = "VALIDATION_FAILED"


def is_api_request(request: Request) -> bool:
    return request.url.path.startswith(API_PREFIX)


def error_json(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse({"detail": detail, "code": code}, status_code=status_code)


async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if is_api_request(request):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)

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
    if is_api_request(request):
        return error_json(exc.status_code, exc.detail, exc.code)

    # 화면 라우트는 리팩터링 전과 같이 로그인 필요를 403, 입력 오류를 400으로 취급한다
    if isinstance(exc, Unauthorized):
        status_code = 403
    elif isinstance(exc, FormError):
        status_code = 400
    else:
        status_code = exc.status_code
    return await custom_http_exception_handler(request, HTTPException(status_code=status_code, detail=exc.detail))


def register_error_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, custom_http_exception_handler)
    app.add_exception_handler(AppError, app_error_handler)
