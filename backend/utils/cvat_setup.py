from backend.database import create_repository
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def initialize_default_cvat_settings() -> None:
    """Ініціалізує дефолтні налаштування для всіх CVAT проєктів"""
    cvat_repo = create_repository("cvat_project_settings", async_mode=False)
    cvat_repo.create_indexes()

    default_settings = [
        {"project_name": "motion-det", "project_id": 5, "overlap": 5, "segment_size": 400, "image_quality": 100},
        {"project_name": "tracking", "project_id": 6, "overlap": 5, "segment_size": 400, "image_quality": 100},
        {"project_name": "mil-hardware", "project_id": 7, "overlap": 5, "segment_size": 400, "image_quality": 100},
        {"project_name": "re-id", "project_id": 8, "overlap": 5, "segment_size": 400, "image_quality": 100},
    ]

    for settings_data in default_settings:
        existing = cvat_repo.find_by_field("project_name", settings_data["project_name"])
        if not existing:
            cvat_repo.save_document(settings_data)
            logger.info(f"Ініціалізовано дефолтні налаштування для {settings_data['project_name']}")