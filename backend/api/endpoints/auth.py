from fastapi import APIRouter, HTTPException

from backend.models.user import LoginRequest, Token, RefreshTokenRequest
from backend.services.auth_service import AuthService
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest) -> Token:
    """Вхід користувача"""
    auth_service = AuthService()

    user = auth_service.authenticate_user(login_data.email, login_data.password)
    if not user:
        logger.warning(f"Невдала спроба входу: {login_data.email}")
        raise HTTPException(
            status_code=401,
            detail="Невірний email або пароль"
        )

    logger.info(f"Успішний вхід: {user['email']}")
    return auth_service.create_tokens(user)


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_data: RefreshTokenRequest) -> Token:
    """Оновлення access токена"""
    auth_service = AuthService()

    token = auth_service.refresh_access_token(refresh_data.refresh_token)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Невалідний refresh token"
        )

    logger.info("Токен успішно оновлено")
    return token