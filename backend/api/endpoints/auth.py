from typing import Annotated
from fastapi import APIRouter, Depends

from backend.models.api import LoginRequest, Token, RefreshTokenRequest, ErrorResponse
from backend.services.auth_service import AuthService
from backend.api.exceptions import AuthenticationException
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=Token,
    summary="Автентифікація користувача",
    description="Перевіряє облікові дані та повертає access і refresh токени",
    responses={
        401: {"model": ErrorResponse, "description": "Невірний email або пароль"},
        422: {"model": ErrorResponse, "description": "Невалідні дані запиту"}
    }
)
async def login(
        login_data: LoginRequest,
        auth_service: Annotated[AuthService, Depends(AuthService)]
) -> Token:
    """Автентифікація користувача та генерація токенів"""
    user = auth_service.authenticate_user(login_data.email, login_data.password)

    if not user:
        logger.warning(f"Failed login attempt: {login_data.email}")
        raise AuthenticationException("Невірний email або пароль")

    logger.info(f"Successful login: {user.email}")
    return auth_service.create_tokens(user)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Оновлення access токена",
    description="Використовує refresh токен для отримання нового access токена",
    responses={
        401: {"model": ErrorResponse, "description": "Невалідний або прострочений refresh токен"},
        422: {"model": ErrorResponse, "description": "Невалідний формат токена"}
    }
)
async def refresh_token(
        refresh_data: RefreshTokenRequest,
        auth_service: Annotated[AuthService, Depends(AuthService)]
) -> Token:
    """Оновлення access токена за допомогою refresh токена"""
    token = auth_service.refresh_access_token(refresh_data.refresh_token)

    if not token:
        logger.warning("Invalid refresh token used")
        raise AuthenticationException("Невалідний або прострочений refresh токен")

    logger.info("Token successfully refreshed")
    return token