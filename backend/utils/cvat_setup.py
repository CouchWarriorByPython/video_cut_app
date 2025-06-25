from backend.services.admin_service import AdminService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def initialize_default_cvat_settings() -> None:
    """Initialize default CVAT settings using AdminService"""
    try:
        admin_service = AdminService()
        admin_service.initialize_default_cvat_settings()
        logger.info("Default CVAT settings initialization completed")

    except Exception as e:
        logger.error(f"Error initializing CVAT settings: {str(e)}")
        raise