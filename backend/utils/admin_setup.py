from backend.database import create_user_repository
from backend.utils.logger import get_logger
from backend.config.settings import get_settings
from backend.utils.password_utils import hash_password, verify_password

settings = get_settings()
logger = get_logger(__name__, "admin_setup.log")


def create_super_admins() -> None:
    """Create or update super admin users based on settings"""
    try:
        user_repo = create_user_repository()

        admins = [
            (settings.super_admin_email_1, settings.super_admin_password_1),
            (settings.super_admin_email_2, settings.super_admin_password_2)
        ]

        for admin_email, admin_password in admins:
            if not admin_email or not admin_password:
                continue

            existing_admin = user_repo.get_by_field("email", admin_email)

            if existing_admin:
                updates = {}

                if not existing_admin.is_active:
                    updates["is_active"] = True

                if existing_admin.role != "super_admin":
                    updates["role"] = "super_admin"
                    logger.warning(f"Fixed super admin role from '{existing_admin.role}' to 'super_admin'")

                if not verify_password(admin_password, existing_admin.hashed_password):
                    updates["hashed_password"] = hash_password(admin_password)
                    logger.info("Updated super admin password according to current settings")

                if updates:
                    success = user_repo.update_by_id(str(existing_admin.id), updates)
                    if success:
                        logger.info(f"Updated super admin fields: {admin_email}")
                    else:
                        logger.error(f"Failed to update super admin: {admin_email}")
                else:
                    logger.info(f"Super admin {admin_email} already exists and is up to date")
                continue

            admin_user = user_repo.create(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                role="super_admin",
                is_active=True
            )

            logger.info(f"Created super admin: {admin_email} (ID: {admin_user.id})")

    except Exception as e:
        logger.error(f"Error creating super admins: {str(e)}")
        raise


def validate_admin_configuration() -> bool:
    """Validate admin configuration from settings"""
    admins = [
        (settings.super_admin_email_1, settings.super_admin_password_1),
        (settings.super_admin_email_2, settings.super_admin_password_2)
    ]

    valid_count = 0

    for admin_email, admin_password in admins:
        if not admin_email or not admin_password:
            continue

        if "@" not in admin_email:
            logger.error(f"Invalid admin email in configuration: {admin_email}")
            continue

        if len(admin_password) < 8:
            logger.error(f"Admin password must contain at least 8 characters for: {admin_email}")
            continue

        valid_count += 1

    if valid_count == 0:
        logger.error("No valid super admin configuration found")
        return False

    return True