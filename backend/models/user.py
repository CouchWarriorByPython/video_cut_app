from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional


class User(BaseModel):
    """Модель користувача"""
    email: EmailStr
    hashed_password: str
    role: str = Field(..., pattern="^(super_admin|admin|annotator)$")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    is_active: bool = True


class UserCreate(BaseModel):
    """Схема створення користувача"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field(..., pattern="^(admin|annotator)$")


class UserUpdateRequest(BaseModel):
    """Схема оновлення користувача"""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    role: Optional[str] = Field(None, pattern="^(admin|annotator)$")


class UserResponse(BaseModel):
    """Схема відповіді користувача"""
    id: str
    email: EmailStr
    role: str
    created_at: str
    is_active: bool


class LoginRequest(BaseModel):
    """Схема логіну"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Схема токена"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Схема рефреш токена"""
    refresh_token: str


class UserCreateResponse(BaseModel):
    """Схема відповіді створення користувача"""
    success: bool
    message: str
    user_id: str | None = None


class UserDeleteResponse(BaseModel):
    """Схема відповіді видалення користувача"""
    success: bool
    message: str