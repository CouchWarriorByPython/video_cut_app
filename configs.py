import os
from typing import Optional, ClassVar, Dict, Any
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

    # Azure Storage
    azure_storage_account_name: ClassVar[str] = ""
    azure_storage_container_name: ClassVar[str] = ""
    azure_output_prefix: ClassVar[str] = ""
    azure_connection_string: ClassVar[Optional[str]] = None

    # CVAT налаштування
    cvat_host: ClassVar[str] = ""
    cvat_port: ClassVar[int] = 8080
    cvat_username: ClassVar[Optional[str]] = None
    cvat_password: ClassVar[Optional[str]] = None

    # CVAT проєкти
    cvat_projects: ClassVar[Dict[str, Dict[str, Any]]] = {}

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

        # Azure Storage
        cls.azure_storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "test_acc")
        cls.azure_storage_container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "test_container")
        cls.azure_output_prefix = os.getenv("AZURE_OUTPUT_PREFIX", "clips")
        cls.azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

        # CVAT налаштування
        cls.cvat_host = os.getenv("CVAT_HOST", "localhost")
        cls.cvat_port = int(os.getenv("CVAT_PORT", "8080"))
        cls.cvat_username = os.getenv("CVAT_USERNAME")
        cls.cvat_password = os.getenv("CVAT_PASSWORD")

        # CVAT проєкти - завантажуємо з env або використовуємо defaults
        cls._load_cvat_projects()

        # Шляхи до файлів
        cls.upload_folder = os.getenv("UPLOAD_FOLDER", "source_videos")
        cls.clips_folder = os.getenv("CLIPS_FOLDER", "clips")
        cls.logs_folder = os.getenv("LOGS_FOLDER", "logs")

        # Логування
        cls.log_level = os.getenv("LOG_LEVEL", "INFO")
        cls.log_max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10MB
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
    def _load_cvat_projects(cls) -> None:
        """Завантаження конфігурації CVAT проєктів з environment variables"""
        # Default конфігурація
        default_projects = {
            "motion-det": {
                "project_id": 22,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            },
            "tracking": {
                "project_id": 17,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            },
            "mil-hardware": {
                "project_id": 10,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            },
            "re-id": {
                "project_id": 17,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            }
        }

        cls.cvat_projects = {}

        for project_name, default_config in default_projects.items():
            project_key = project_name.upper().replace("-", "_")

            # Завантажуємо конфігурацію кожного проєкту з env
            cls.cvat_projects[project_name] = {
                "project_id": int(os.getenv(f"CVAT_{project_key}_PROJECT_ID", str(default_config["project_id"]))),
                "overlap": int(os.getenv(f"CVAT_{project_key}_OVERLAP", str(default_config["overlap"]))),
                "segment_size": int(os.getenv(f"CVAT_{project_key}_SEGMENT_SIZE", str(default_config["segment_size"]))),
                "image_quality": int(
                    os.getenv(f"CVAT_{project_key}_IMAGE_QUALITY", str(default_config["image_quality"])))
            }
            print(f"--->>> {cls.cvat_projects} <<<----")

    @classmethod
    def _create_directories(cls) -> None:
        """Створює необхідні директорії"""
        for folder in [cls.upload_folder, cls.clips_folder, cls.logs_folder]:
            Path(folder).mkdir(exist_ok=True)

    @classmethod
    def get_cvat_project_params(cls, project_name: str) -> Optional[Dict[str, Any]]:
        """Повертає параметри проєкту CVAT"""
        return cls.cvat_projects.get(project_name)

    @classmethod
    def validate_cvat_config(cls) -> bool:
        """Перевіряє наявність необхідних CVAT налаштувань"""
        return cls.cvat_username is not None and cls.cvat_password is not None

    @classmethod
    def validate_azure_config(cls) -> bool:
        """Перевіряє наявність необхідних Azure налаштувань"""
        return cls.azure_connection_string is not None

    @classmethod
    def get_all_env_vars(cls) -> Dict[str, str]:
        """Повертає словник всіх поточних налаштувань для діагностики"""
        return {
            "mongo_uri": cls.mongo_uri,
            "mongo_db_name": cls.mongo_db_name,
            "redis_url": cls.redis_url,
            "azure_storage_account_name": cls.azure_storage_account_name,
            "azure_storage_container_name": cls.azure_storage_container_name,
            "cvat_host": cls.cvat_host,
            "cvat_port": str(cls.cvat_port),
            "cvat_username": cls.cvat_username or "NOT_SET",
            "upload_folder": cls.upload_folder,
            "clips_folder": cls.clips_folder,
            "logs_folder": cls.logs_folder,
            "log_level": cls.log_level,
            "host": cls.host,
            "port": str(cls.port),
            "reload": str(cls.reload)
        }


# Ініціалізація налаштувань при імпорті
Settings.load_from_env()