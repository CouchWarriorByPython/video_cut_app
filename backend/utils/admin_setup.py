from backend.database import create_user_repository
from backend.utils.logger import get_logger
from backend.config.settings import get_settings
from backend.utils.password_utils import hash_password, verify_password

settings = get_settings()
logger = get_logger(__name__, "admin_setup.log")


def create_super_admin() -> None:
    """Create or update super admin user based on settings"""
    try:
        user_repo = create_user_repository()
        existing_admin = user_repo.get_by_field("email", settings.super_admin_email)

        if existing_admin:
            updates = {}

            if not existing_admin.is_active:
                updates["is_active"] = True

            if existing_admin.role != "super_admin":
                updates["role"] = "super_admin"
                logger.warning(f"Fixed super admin role from '{existing_admin.role}' to 'super_admin'")

            if not verify_password(settings.super_admin_password, existing_admin.hashed_password):
                updates["hashed_password"] = hash_password(settings.super_admin_password)
                logger.info("Updated super admin password according to current settings")

            if updates:
                success = user_repo.update_by_id(str(existing_admin.id), updates)
                if success:
                    logger.info(f"Updated super admin fields: {settings.super_admin_email}")
                else:
                    logger.error(f"Failed to update super admin: {settings.super_admin_email}")
            else:
                logger.info(f"Super admin {settings.super_admin_email} already exists and is up to date")
            return

        admin_user = user_repo.create(
            email=settings.super_admin_email,
            hashed_password=hash_password(settings.super_admin_password),
            role="super_admin",
            is_active=True
        )

        logger.info(f"Created super admin: {settings.super_admin_email} (ID: {admin_user.id})")

    except Exception as e:
        logger.error(f"Error creating super admin: {str(e)}")
        raise


def validate_admin_configuration() -> bool:
    """Validate admin configuration from settings"""
    if not settings.super_admin_email or "@" not in settings.super_admin_email:
        logger.error("Invalid admin email in configuration")
        return False

    if not settings.super_admin_password or len(settings.super_admin_password) < 8:
        logger.error("Admin password must contain at least 8 characters")
        return False

    return True