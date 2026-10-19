"""
도메인 예외와 예외 핸들러.

service는 HTTP를 모르므로 HTTPException 대신 아래 예외를 발생시킨다.
핸들러가 {"detail": 메시지, "code": 코드} JSON과 상태 코드로 변환한다.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LOGIN_REQUIRED = "로그인이 필요합니다."


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
    """사용자 입력 오류. 422로 응답한다."""
    status_code = 422
    code = "VALIDATION_FAILED"


def error_json(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse({"detail": detail, "code": code}, status_code=status_code)


async def app_error_handler(request: Request, exc: AppError):
    return error_json(exc.status_code, exc.detail, exc.code)


def register_error_handlers(app: FastAPI):
    app.add_exception_handler(AppError, app_error_handler)
