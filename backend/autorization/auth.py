from fastapi import APIRouter, HTTPException, status, Depends
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.gcp_tools.logging import get_logger
from backend.autorization.utils import authenticate_user, generate_tokens, decode_token
from backend.database.connector import get_db
from backend.schemas import Token, RefreshTokenRequest, LoginRequest

logger = get_logger()
router = APIRouter()


@router.post("/login/", response_model=Token)
async def login_for_access_token(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> Token:
    """ Endpoint for obtaining access tokens after login """
    logger.info(f"🔑 Login request received for {request.email}")

    user = await authenticate_user(db, request.email, request.password)
    if not user:
        logger.warning(f"❌ Failed login attempt for {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"✅ Successful login for {request.email}")
    return await generate_tokens(user.email, user.role)


@router.post("/token/refresh/", response_model=Token)
async def refresh_access_token(request_data: RefreshTokenRequest) -> Token:
    """ Endpoint for refreshing access tokens """
    logger.info("🔄 Token refresh request received")

    try:
        payload = await decode_token(request_data.refresh_token)
        if not payload:
            logger.error("⚠️ Invalid or expired token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        email, role = payload.get("sub"), payload.get("role")

        if not email or not role:
            logger.error(f"⚠️ Invalid payload in refresh token: {payload}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

        logger.info(f"🔄 Token refreshed for {email}")
        return await generate_tokens(email, role)

    except JWTError as e:
        logger.error(f"⛔ Error while refreshing refresh token: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
