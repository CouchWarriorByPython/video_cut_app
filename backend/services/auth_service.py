from datetime import datetime, UTC, timedelta, timezone
from typing import Dict, Any, Optional
from jose import jwt, JWTError
from pydantic import EmailStr
from passlib.context import CryptContext

from backend.database import create_repository
from backend.models.user import Token
from backend.utils.logger import get_logger
from backend.config.settings import get_settings

logger = get_logger(__name__, "services.log")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Сервіс авторизації"""

    def __init__(self):
        self.user_repo = create_repository("users", async_mode=False)
        self.settings = get_settings()

    def authenticate_user(self, email: EmailStr, password: str) -> Optional[Dict]:
        """Аутентифікує користувача"""
        try:
            user = self.user_repo.find_by_field("email", str(email))
            if not user:
                return None

            if not self._verify_password(password, user["hashed_password"]):
                return None

            return user
        except Exception as e:
            logger.error(f"Помилка аутентифікації: {str(e)}")
            return None

    def create_tokens(self, user: Dict) -> Token:
        """Створює токени доступу та оновлення"""
        try:
            now = datetime.now(timezone.utc)

            token_data = {
                "sub": user["email"],
                "user_id": user["_id"],
                "role": user["role"]
            }

            access_expire = now + timedelta(minutes=self.settings.access_token_expire_minutes)
            access_token = jwt.encode(
                {**token_data, "exp": access_expire, "type": "access"},
                self.settings.secret_key,
                algorithm=self.settings.jwt_algorithm
            )

            refresh_expire = now + timedelta(minutes=self.settings.refresh_token_expire_minutes)
            refresh_token = jwt.encode(
                {**token_data, "exp": refresh_expire, "type": "refresh"},
                self.settings.secret_key,
                algorithm=self.settings.jwt_algorithm
            )

            return Token(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer"
            )

        except Exception as e:
            logger.error(f"Помилка створення токенів: {str(e)}")
            raise

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict]:
        """Перевіряє та декодує токен"""
        try:
            payload = jwt.decode(token, self.settings.secret_key, algorithms=[self.settings.jwt_algorithm])

            if payload.get("type") != token_type:
                return None

            return payload

        except JWTError as e:
            logger.warning(f"Невалідний токен: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Помилка перевірки токена: {str(e)}")
            return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Token]:
        """Оновлює access token за допомогою refresh token"""
        try:
            payload = self.verify_token(refresh_token, "refresh")
            if not payload:
                return None

            user = self.user_repo.find_by_field("email", payload["sub"])
            if not user:
                return None

            return self.create_tokens(user)

        except Exception as e:
            logger.error(f"Помилка оновлення токена: {str(e)}")
            return None

    def create_user(self, email: EmailStr, password: str, role: str) -> Dict[str, Any]:
        """Створює нового користувача"""
        try:
            self.user_repo.create_indexes()

            existing_user = self.user_repo.find_by_field("email", str(email))
            if existing_user:
                return {"success": False, "error": "Користувач з таким email вже існує"}

            user_data = {
                "email": str(email),
                "hashed_password": self._hash_password(password),
                "role": role,
                "is_active": True,
                "created_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds"),
                "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            }

            user_id = self.user_repo.save_document(user_data)

            return {
                "success": True,
                "user_id": user_id,
                "message": f"Користувача {email} створено успішно"
            }

        except Exception as e:
            logger.error(f"Помилка створення користувача: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Отримує інформацію про користувача"""
        try:
            return self.user_repo.find_by_id(user_id)
        except Exception as e:
            logger.error(f"Помилка отримання користувача: {str(e)}")
            return None

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Перевіряє пароль"""
        return pwd_context.verify(plain_password, hashed_password)

    def _hash_password(self, password: str) -> str:
        """Хешує пароль"""
        return pwd_context.hash(password)
