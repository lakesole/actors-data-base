from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

LOGIN_REQUIRED = "로그인이 필요합니다."


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


def register_error_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, custom_http_exception_handler)
