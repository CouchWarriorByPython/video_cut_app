from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from pydantic import EmailStr

from backend.database import create_user_repository
from backend.models.api import Token, CurrentUser, TokenPayload
from backend.models.shared import UserRole
from backend.models.documents import UserDocument
from backend.utils.password_utils import verify_password, hash_password
from backend.api.exceptions import ValidationException, ConflictException, BusinessLogicException
from backend.utils.logger import get_logger
from backend.config.settings import get_settings

logger = get_logger(__name__, "services.log")


class AuthService:
    """Service for authentication and authorization operations"""

    def __init__(self):
        self.user_repo = create_user_repository()
        self.settings = get_settings()

    def authenticate_user(self, email: EmailStr, password: str) -> Optional[CurrentUser]:
        """
        Authenticate user and return CurrentUser model

        Returns None if authentication fails
        """
        try:
            user = self.user_repo.get_by_field("email", str(email))
            if not user:
                return None

            if not user.is_active:
                logger.warning(f"Inactive user login attempt: {email}")
                return None

            if not verify_password(password, user.hashed_password):
                return None

            # Update last login
            self.user_repo.update_by_id(
                str(user.id),
                {"last_login_at_utc": datetime.now(timezone.utc)}
            )

            return CurrentUser.from_document(user)

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None

    def create_tokens(self, user: CurrentUser) -> Token:
        """
        Create JWT access and refresh tokens from CurrentUser

        Raises BusinessLogicException if token creation fails
        """
        try:
            now = datetime.now(timezone.utc)

            # Create access token
            access_payload = TokenPayload(
                sub=user.email,
                user_id=user.user_id,
                role=user.role,
                exp=int((now + timedelta(minutes=self.settings.access_token_expire_minutes)).timestamp()),
                type="access"
            )
            access_token = self._encode_token(access_payload.model_dump())

            # Create refresh token
            refresh_payload = TokenPayload(
                sub=user.email,
                user_id=user.user_id,
                role=user.role,
                exp=int((now + timedelta(minutes=self.settings.refresh_token_expire_minutes)).timestamp()),
                type="refresh"
            )
            refresh_token = self._encode_token(refresh_payload.model_dump())

            return Token(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer"
            )

        except Exception as e:
            logger.error(f"Token creation error: {str(e)}")
            raise BusinessLogicException(f"Помилка створення токенів: {str(e)}")

    def verify_token(self, token: str, token_type: str = "access") -> Optional[TokenPayload]:
        """
        Verify JWT token and return TokenPayload

        Returns None if token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.jwt_algorithm]
            )

            token_payload = TokenPayload(**payload)

            if token_payload.type != token_type:
                return None

            # For access tokens, verify user is still active
            if token_type == "access":
                user = self.user_repo.get_by_id(token_payload.user_id)
                if not user or not user.is_active:
                    return None

            return token_payload

        except (JWTError, ValueError) as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Token]:
        """
        Refresh access token using refresh token

        Returns None if refresh fails
        """
        try:
            payload = self.verify_token(refresh_token, "refresh")
            if not payload:
                return None

            user = self.user_repo.get_by_id(payload.user_id)
            if not user or not user.is_active:
                return None

            current_user = CurrentUser.from_document(user)
            return self.create_tokens(current_user)

        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return None

    def create_user(self, email: EmailStr, password: str, role: str) -> UserDocument:
        """
        Create new user with validation

        Raises:
            ValidationException: If validation fails
            ConflictException: If user already exists
            BusinessLogicException: If creation fails
        """
        try:
            # Validate role
            if role not in [r.value for r in UserRole]:
                raise ValidationException(
                    "Невалідна роль користувача",
                    {"allowed_roles": [r.value for r in UserRole]}
                )

            # Check existence
            if self.user_repo.exists(email=str(email)):
                raise ConflictException(
                    "Користувач з таким email вже існує",
                    {"email": str(email)}
                )

            # Validate password
            if len(password) < 8:
                raise ValidationException(
                    "Пароль повинен містити мінімум 8 символів",
                    {"field": "password", "min_length": 8}
                )

            # Create user
            user = self.user_repo.create(
                email=str(email),
                hashed_password=hash_password(password),
                role=role,
                is_active=True
            )

            logger.info(f"User created: {email} with role {role}")
            return user

        except (ValidationException, ConflictException):
            raise
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            raise BusinessLogicException(f"Помилка створення користувача: {str(e)}")

    def get_current_user_from_token(self, token: str) -> Optional[CurrentUser]:
        """Get CurrentUser from access token"""
        payload = self.verify_token(token, "access")
        if not payload:
            return None

        return CurrentUser(
            user_id=payload.user_id,
            email=payload.sub,
            role=payload.role,
            is_active=True
        )

    def _encode_token(self, payload: dict) -> str:
        """Encode JWT token"""
        return jwt.encode(
            payload,
            self.settings.secret_key,
            algorithm=self.settings.jwt_algorithm
        )