import aiosqlite
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import current_user, require_login
from app.core.database import get_db
from app.core.errors import Forbidden, FormError
from app.core.templating import templates
from app.features.auth import service

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: dict | None = Depends(current_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "",
        "current_user": None,
    })


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        user = await service.authenticate(db, username, password)
    except FormError as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": e.detail,
            "current_user": None,
        })

    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/account/password", response_class=HTMLResponse)
async def account_password_page(request: Request, user: dict = Depends(require_login)):
    return templates.TemplateResponse("account_password.html", {
        "request": request,
        "current_user": user,
        "error": "",
        "success": request.query_params.get("success", ""),
    })


@router.post("/account/password", response_class=HTMLResponse)
async def account_password_change(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        await service.change_password(db, user, current_password, new_password, new_password_confirm)
    except FormError as e:
        return templates.TemplateResponse("account_password.html", {
            "request": request,
            "current_user": user,
            "error": e.detail,
            "success": "",
        })
    except Forbidden:
        request.session.clear()
        raise

    return RedirectResponse(url="/account/password?success=changed", status_code=303)
