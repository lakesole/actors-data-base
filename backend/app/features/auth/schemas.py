from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str
    new_password_confirm: str


class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
