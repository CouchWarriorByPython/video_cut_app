import os
from typing import Optional, ClassVar
from dotenv import load_dotenv
from pathlib import Path


class Settings:
    """Централізовані налаштування програми з завантаженням з environment variables"""

    # MongoDB
    mongo_uri: ClassVar[str] = ""
    mongo_db_name: ClassVar[str] = ""

    # Redis/Celery
    redis_url: ClassVar[str] = ""
    celery_broker_url: ClassVar[str] = ""
    celery_result_backend: ClassVar[str] = ""

    # Azure Storage - нові поля для service principal
    azure_tenant_id: ClassVar[Optional[str]] = None
    azure_client_id: ClassVar[Optional[str]] = None
    azure_client_secret: ClassVar[Optional[str]] = None
    azure_storage_account_name: ClassVar[str] = ""
    azure_storage_container_name: ClassVar[str] = ""
    azure_folder_path: ClassVar[str] = ""  # замість output_prefix
    azure_mock_mode: ClassVar[bool] = False

    # CVAT налаштування
    cvat_host: ClassVar[str] = ""
    cvat_port: ClassVar[int] = 8080
    cvat_username: ClassVar[Optional[str]] = None
    cvat_password: ClassVar[Optional[str]] = None
    cvat_mock_mode: ClassVar[bool] = False

    # Шляхи до файлів
    upload_folder: ClassVar[str] = ""
    clips_folder: ClassVar[str] = ""
    logs_folder: ClassVar[str] = ""

    # Логування
    log_level: ClassVar[str] = ""
    log_max_bytes: ClassVar[int] = 0
    log_backup_count: ClassVar[int] = 0

    # Відео обробка
    default_fps: ClassVar[int] = 0
    ffmpeg_log_level: ClassVar[str] = ""

    # Веб сервер
    host: ClassVar[str] = ""
    port: ClassVar[int] = 0
    reload: ClassVar[bool] = False

    @classmethod
    def load_from_env(cls) -> None:
        """Завантаження всіх налаштувань із .env файлу та змінних середовища"""
        load_dotenv()

        # MongoDB
        cls.mongo_uri = os.getenv("MONGO_URI", "mongodb://anot_user:anot_pass@localhost:27017/annotator")
        cls.mongo_db_name = os.getenv("MONGO_DB", "annotator")

        # Redis/Celery
        redis_default = "redis://localhost:6379/0"
        cls.redis_url = os.getenv("REDIS_URL", redis_default)
        cls.celery_broker_url = os.getenv("CELERY_BROKER_URL", cls.redis_url)
        cls.celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", cls.redis_url)

        # Azure Storage - service principal credentials
        cls.azure_tenant_id = os.getenv("AZURE_TENANT_ID")
        cls.azure_client_id = os.getenv("AZURE_CLIENT_ID")
        cls.azure_client_secret = os.getenv("AZURE_CLIENT_SECRET")
        cls.azure_storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "jettadatashared")
        cls.azure_storage_container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "ml-data")
        cls.azure_folder_path = os.getenv("AZURE_FOLDER_PATH", "annotation/my_test_folder/")
        cls.azure_mock_mode = os.getenv("AZURE_MOCK_MODE", "true").lower() in ("true", "1", "yes")

        # CVAT налаштування
        cls.cvat_host = os.getenv("CVAT_HOST", "localhost")
        cls.cvat_port = int(os.getenv("CVAT_PORT", "8080"))
        cls.cvat_username = os.getenv("CVAT_USERNAME")
        cls.cvat_password = os.getenv("CVAT_PASSWORD")
        cls.cvat_mock_mode = os.getenv("CVAT_MOCK_MODE", "true").lower() in ("true", "1", "yes")

        # Шляхи до файлів
        cls.upload_folder = os.getenv("UPLOAD_FOLDER", "source_videos")
        cls.clips_folder = os.getenv("CLIPS_FOLDER", "clips")
        cls.logs_folder = os.getenv("LOGS_FOLDER", "logs")

        # Логування
        cls.log_level = os.getenv("LOG_LEVEL", "INFO")
        cls.log_max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        cls.log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

        # Відео обробка
        cls.default_fps = int(os.getenv("DEFAULT_FPS", "60"))
        cls.ffmpeg_log_level = os.getenv("FFMPEG_LOG_LEVEL", "error")

        # Веб сервер
        cls.host = os.getenv("HOST", "localhost")
        cls.port = int(os.getenv("PORT", "8000"))
        cls.reload = os.getenv("RELOAD", "true").lower() in ("true", "1", "yes")

        # Створюємо необхідні директорії
        cls._create_directories()

    @classmethod
    def _create_directories(cls) -> None:
        """Створює необхідні директорії"""
        for folder in [cls.upload_folder, cls.clips_folder, cls.logs_folder]:
            Path(folder).mkdir(exist_ok=True)

    @classmethod
    def validate_cvat_config(cls) -> bool:
        """Перевіряє наявність необхідних CVAT налаштувань"""
        return (cls.cvat_username is not None and cls.cvat_password is not None) or cls.cvat_mock_mode

    @classmethod
    def validate_azure_config(cls) -> bool:
        """Перевіряє наявність необхідних Azure налаштувань"""
        required_fields = [cls.azure_tenant_id, cls.azure_client_id, cls.azure_client_secret]
        return all(field is not None for field in required_fields) or cls.azure_mock_mode


# Ініціалізація налаштувань при імпорті
Settings.load_from_env()