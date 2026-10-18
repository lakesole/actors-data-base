from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: str


class UserCreateIn(BaseModel):
    username: str
    password: str
    password_confirm: str
    display_name: str
    role: str


class UserUpdateIn(BaseModel):
    """보낸 값만 바꾼다."""
    is_active: bool | None = None
    role: str | None = None


class PasswordResetIn(BaseModel):
    new_password: str
    new_password_confirm: str
