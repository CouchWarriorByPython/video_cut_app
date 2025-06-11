from datetime import datetime, timedelta, timezone
from jose import jwt, ExpiredSignatureError, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Depends
from sqlalchemy import select, cast

from backend.database.models import User as DBUser
from backend.config import config
from backend.autorization import dependencies
from backend.schemas import Token
from backend.gcp_tools.logging import get_logger
from sqlalchemy.types import String
from pydantic import EmailStr


logger = get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies that the password matches the hash (synchronous operation)"""
    return pwd_context.verify(plain_password, hashed_password)


async def get_password_hash(password: str) -> str:
    """Hashes the password (synchronous operation)"""
    return pwd_context.hash(password)


async def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        logger.info(f"🔍 Successfully decoded token for {payload.get('sub')}")

        exp = payload.get("exp")
        if exp:
            exp_time = datetime.fromtimestamp(exp, timezone.utc)
            now = datetime.now(timezone.utc)
            if exp_time < now:
                logger.warning(f"⛔ Token expired! {payload.get('sub')}, exp: {exp_time}, now: {now}")
                return None

        return payload

    except ExpiredSignatureError:
        logger.warning("⛔ Token expired!")
        return None

    except JWTError:
        logger.error("⛔ Invalid token!")
        return None


async def authenticate_user(db: AsyncSession, email: EmailStr, password: str) -> DBUser | bool:
    result = await db.execute(select(DBUser).where(cast(DBUser.email, String) == str(email)))
    user = result.scalars().first()

    if not user:
        logger.warning(f"❌ Login attempt with unknown email: {email}")
        return False

    if not await verify_password(password, user.hashed_password):
        logger.warning(f"❌ Incorrect password for {email}")
        return False

    logger.info(f"✅ Successful authentication for {email}")
    return user


async def require_owner(current_user: dict[str, str] = Depends(dependencies.get_current_user)) -> dict[str, str]:
    """Dependency to check for owner role"""
    if current_user["role"] != "owner":
        logger.warning(f"🚫 Access denied for {current_user['email']}, 'owner' role required")
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


async def validate_email(email: EmailStr) -> EmailStr:
    """Validation to ensure email is from an allowed domain."""
    with open(config.ALLOWED_EMAILS_FILE, 'r', encoding='utf-8') as file:
        allowed_domains = {line.strip() for line in file}

    email_domain = str(email).split("@")[-1]

    if email_domain not in allowed_domains:
        logger.warning(f"🚨 Invalid email domain: {email}")
        raise HTTPException(status_code=400, detail="Email must be from an allowed company domain")

    return email


async def generate_tokens(email: str, role: str) -> Token:
    """Generates a pair of tokens (access_token and refresh_token) for the user."""
    logger.info(f"🔄 Generating tokens for {email} ({role})")
    now = datetime.now(timezone.utc)
    data = {"sub": email, "role": role}

    access_expire = now + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expire = now + timedelta(minutes=config.REFRESH_TOKEN_EXPIRE_MINUTES)

    access_token = jwt.encode(
        {**data, "exp": access_expire.timestamp()},
        config.SECRET_KEY,
        algorithm=config.ALGORITHM
    )
    refresh_token = jwt.encode(
        {**data, "exp": refresh_expire.timestamp()},
        config.SECRET_KEY,
        algorithm=config.ALGORITHM
    )
    logger.info(f"🔑 Tokens created for {email} ({role})")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


async def require_admin_or_owner(
    current_user: dict[str, str] = Depends(dependencies.get_current_user)
) -> dict[str, str]:
    """Checks that the user has the 'admin' or 'owner' role."""
    if current_user["role"] not in ["admin", "owner"]:
        logger.warning(f"🚫 Access denied for {current_user['email']}, 'admin' or 'owner' role required")
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user
