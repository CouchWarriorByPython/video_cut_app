from backend.database import create_repository
from backend.utils.logger import get_logger
from backend.config.settings import Settings
from datetime import datetime
from passlib.context import CryptContext

logger = get_logger(__name__, "admin_setup.log")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_super_admin() -> None:
    """Створює супер адміна якщо його немає"""
    try:
        user_repo = create_repository("users", async_mode=False)
        user_repo.create_indexes()

        existing_admin = user_repo.find_by_field("email", Settings.admin_email)

        if existing_admin:
            current_time = datetime.now().isoformat(sep=" ", timespec="seconds")
            updates = {}

            # Перевірка та підготовка оновлень відсутніх полів
            if "created_at" not in existing_admin:
                updates["created_at"] = current_time

            if "updated_at" not in existing_admin:
                updates["updated_at"] = current_time

            if "is_active" not in existing_admin or not existing_admin["is_active"]:
                updates["is_active"] = True

            # Критично важливо: перевірка ролі супер адміна
            if existing_admin["role"] != "super_admin":
                updates["role"] = "super_admin"
                logger.warning(f"Виправлено роль супер адміна з '{existing_admin['role']}' на 'super_admin'")

            # Оновлення пароля якщо змінився в конфігурації
            if not verify_password(Settings.admin_password, existing_admin["hashed_password"]):
                updates["hashed_password"] = hash_password(Settings.admin_password)
                logger.info("Оновлено пароль супер адміна згідно з поточними налаштуваннями")

            if updates:
                success = user_repo.update_by_id(existing_admin["_id"], updates)
                if success:
                    logger.info(f"Оновлено поля супер адміна: {Settings.admin_email}")
                else:
                    logger.error(f"Не вдалося оновити супер адміна: {Settings.admin_email}")
            else:
                logger.info(f"Супер адмін {Settings.admin_email} вже існує та актуальний")
            return

        # Створення нового супер адміна
        admin_data = {
            "email": Settings.admin_email,
            "hashed_password": hash_password(Settings.admin_password),
            "role": "super_admin",
            "is_active": True,
            "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
        }

        admin_id = user_repo.save_document(admin_data)
        logger.info(f"Створено супер адміна: {Settings.admin_email} (ID: {admin_id})")

    except Exception as e:
        logger.error(f"Помилка створення супер адміна: {str(e)}")
        raise


def validate_admin_configuration() -> bool:
    """Валідує конфігурацію адміністратора"""
    if not Settings.admin_email or "@" not in Settings.admin_email:
        logger.error("Невірний email адміністратора в конфігурації")
        return False

    if not Settings.admin_password or len(Settings.admin_password) < 8:
        logger.error("Пароль адміністратора повинен містити мінімум 8 символів")
        return False

    return True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Перевіряє пароль"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Хешує пароль"""
    return pwd_context.hash(password)