from backend.database import create_repository
from backend.utils.logger import get_logger
from backend.config.settings import get_settings

from datetime import datetime, UTC
from passlib.context import CryptContext

settings = get_settings()
logger = get_logger(__name__, "admin_setup.log")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_super_admin() -> None:
    """Створює супер адміна якщо його немає"""
    try:
        user_repo = create_repository("users", async_mode=False)
        user_repo.create_indexes()

        existing_admin = user_repo.find_by_field("email", settings.super_admin_email)

        if existing_admin:
            current_time = datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            updates = {}

            if "created_at_utc" not in existing_admin:
                updates["created_at_utc"] = current_time

            if "updated_at_utc" not in existing_admin:
                updates["updated_at_utc"] = current_time

            if "is_active" not in existing_admin or not existing_admin["is_active"]:
                updates["is_active"] = True

            if existing_admin["role"] != "super_admin":
                updates["role"] = "super_admin"
                logger.warning(f"Виправлено роль супер адміна з '{existing_admin['role']}' на 'super_admin'")

            if not verify_password(settings.super_admin_password, existing_admin["hashed_password"]):
                updates["hashed_password"] = hash_password(settings.super_admin_password)
                logger.info("Оновлено пароль супер адміна згідно з поточними налаштуваннями")

            if updates:
                success = user_repo.update_by_id(existing_admin["_id"], updates)
                if success:
                    logger.info(f"Оновлено поля супер адміна: {settings.super_admin_email}")
                else:
                    logger.error(f"Не вдалося оновити супер адміна: {settings.super_admin_email}")
            else:
                logger.info(f"Супер адмін {settings.super_admin_email} вже існує та актуальний")
            return

        admin_data = {
            "email": settings.super_admin_email,
            "hashed_password": hash_password(settings.super_admin_password),
            "role": "super_admin",
            "is_active": True,
            "created_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds"),
            "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
        }

        admin_id = user_repo.save_document(admin_data)
        logger.info(f"Створено супер адміна: {settings.super_admin_email} (ID: {admin_id})")

    except Exception as e:
        logger.error(f"Помилка створення супер адміна: {str(e)}")
        raise


def validate_admin_configuration() -> bool:
    """Валідує конфігурацію адміністратора"""
    if not settings.super_admin_email or "@" not in settings.super_admin_email:
        logger.error("Невірний email адміністратора в конфігурації")
        return False

    if not settings.super_admin_password or len(settings.super_admin_password) < 8:
        logger.error("Пароль адміністратора повинен містити мінімум 8 символів")
        return False

    return True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Перевіряє пароль"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Хешує пароль"""
    return pwd_context.hash(password)
