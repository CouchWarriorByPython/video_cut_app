from backend.database.repositories.user import UserRepository
from backend.utils.logger import get_logger
from backend.config.settings import Settings

logger = get_logger(__name__, "admin_setup.log")


def create_super_admin() -> None:
    """Створює супер адміна якщо його немає"""
    try:
        user_repo = UserRepository()
        user_repo.create_indexes()

        # Перевіряємо чи існує супер адмін
        existing_admin = user_repo.get_user_by_email(Settings.admin_email)

        if existing_admin:
            logger.info(f"Супер адмін {Settings.admin_email} вже існує")
            return

        # Створюємо супер адміна
        admin_id = user_repo.create_user(Settings.admin_email, Settings.admin_password, "super_admin")
        logger.info(f"Створено супер адміна: {Settings.admin_email} (ID: {admin_id})")

    except Exception as e:
        logger.error(f"Помилка створення супер адміна: {str(e)}")
        raise