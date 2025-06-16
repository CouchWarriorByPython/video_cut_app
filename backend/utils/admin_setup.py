# backend/utils/admin_setup.py
from backend.database.repositories.user import UserRepository
from backend.utils.logger import get_logger
from backend.config.settings import Settings
from datetime import datetime

logger = get_logger(__name__, "admin_setup.log")


def create_super_admin() -> None:
    """Створює супер адміна якщо його немає"""
    try:
        user_repo = UserRepository()
        user_repo.create_indexes()

        existing_admin = user_repo.get_user_by_email(Settings.admin_email)

        if existing_admin:
            needs_update = False
            updates = {}
            current_time = datetime.now().isoformat(sep=" ", timespec="seconds")

            # Перевірка та оновлення відсутніх полів
            if "created_at" not in existing_admin:
                updates["created_at"] = current_time
                needs_update = True

            if "updated_at" not in existing_admin:
                updates["updated_at"] = current_time
                needs_update = True

            if "is_active" not in existing_admin or not existing_admin["is_active"]:
                updates["is_active"] = True
                needs_update = True

            # Критично важливо: перевірка ролі супер адміна
            if existing_admin["role"] != "super_admin":
                updates["role"] = "super_admin"
                needs_update = True
                logger.warning(f"Виправлено роль супер адміна з '{existing_admin['role']}' на 'super_admin'")

            # Оновлення пароля якщо змінився в конфігурації
            if not user_repo.verify_password(Settings.admin_password, existing_admin["hashed_password"]):
                updates["hashed_password"] = user_repo.hash_password(Settings.admin_password)
                needs_update = True
                logger.info("Оновлено пароль супер адміна згідно з поточними налаштуваннями")

            if needs_update:
                user_repo.update_user(existing_admin["_id"], updates)
                logger.info(f"Оновлено поля супер адміна: {Settings.admin_email}")
            else:
                logger.info(f"Супер адмін {Settings.admin_email} вже існує та актуальний")
            return

        # Створення нового супер адміна
        admin_id = user_repo.create_user(Settings.admin_email, Settings.admin_password, "super_admin")
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