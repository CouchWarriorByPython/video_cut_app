import os
from typing import ClassVar
from dotenv import load_dotenv
from pathlib import Path


class Settings:
    """Централізовані налаштування програми з завантаженням з .env файлу"""

    # MongoDB
    mongo_uri: ClassVar[str] = ""
    mongo_db_name: ClassVar[str] = ""

    # Redis/Celery
    redis_url: ClassVar[str] = ""
    celery_broker_url: ClassVar[str] = ""
    celery_result_backend: ClassVar[str] = ""

    # Azure Storage - service principal credentials
    azure_tenant_id: ClassVar[str] = ""
    azure_client_id: ClassVar[str] = ""
    azure_client_secret: ClassVar[str] = ""
    azure_storage_account_name: ClassVar[str] = ""
    azure_storage_container_name: ClassVar[str] = ""
    azure_input_folder_path: ClassVar[str] = ""
    azure_output_folder_path: ClassVar[str] = ""

    # CVAT налаштування
    cvat_host: ClassVar[str] = ""
    cvat_port: ClassVar[int] = 8080
    cvat_username: ClassVar[str] = ""
    cvat_password: ClassVar[str] = ""

    # Тимчасові шляхи для обробки
    temp_folder: ClassVar[str] = ""
    logs_folder: ClassVar[str] = ""

    # Логування
    log_level: ClassVar[str] = ""
    log_max_bytes: ClassVar[int] = 0
    log_backup_count: ClassVar[int] = 0

    # Відео обробка
    ffmpeg_log_level: ClassVar[str] = ""

    # Веб сервер
    host: ClassVar[str] = ""
    port: ClassVar[int] = 0
    reload: ClassVar[bool] = False

    # Оптимізація завантаження
    azure_download_chunk_size: ClassVar[int] = 16777216
    azure_max_concurrency: ClassVar[int] = 4

    @classmethod
    def load_from_env(cls) -> None:
        """Завантаження налаштувань з .env файлу"""
        load_dotenv(".env", override=True)

        # MongoDB - обов'язкові
        cls.mongo_uri = os.getenv("MONGO_URI", "")
        cls.mongo_db_name = os.getenv("MONGO_DB", "video_annotator")

        # Redis/Celery - обов'язкові
        cls.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        cls.celery_broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
        cls.celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

        # Azure Storage - обов'язкові credentials
        cls.azure_tenant_id = os.getenv("AZURE_TENANT_ID", "")
        cls.azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
        cls.azure_client_secret = os.getenv("AZURE_CLIENT_SECRET", "")
        cls.azure_storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "")
        cls.azure_storage_container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "")
        cls.azure_input_folder_path = os.getenv("AZURE_INPUT_FOLDER_PATH", "input/")
        cls.azure_output_folder_path = os.getenv("AZURE_OUTPUT_FOLDER_PATH", "output/")

        # CVAT налаштування - обов'язкові
        cls.cvat_host = os.getenv("CVAT_HOST", "localhost")
        cls.cvat_port = int(os.getenv("CVAT_PORT", "8080"))
        cls.cvat_username = os.getenv("CVAT_USERNAME", "")
        cls.cvat_password = os.getenv("CVAT_PASSWORD", "")

        # Тимчасові шляхи - з дефолтами
        cls.temp_folder = os.getenv("TEMP_FOLDER", "temp")
        cls.logs_folder = os.getenv("LOGS_FOLDER", "logs")

        # Логування - з дефолтами
        cls.log_level = os.getenv("LOG_LEVEL", "INFO")
        cls.log_max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        cls.log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

        # Відео обробка - з дефолтами
        cls.ffmpeg_log_level = os.getenv("FFMPEG_LOG_LEVEL", "error")

        # Веб сервер - з дефолтами
        cls.host = os.getenv("HOST", "0.0.0.0")
        cls.port = int(os.getenv("PORT", "8000"))
        cls.reload = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")

        # Створюємо необхідні директорії
        cls._create_directories()

        # Валідуємо обов'язкові налаштування
        cls._validate_required_settings()

    @classmethod
    def _create_directories(cls) -> None:
        """Створює необхідні директорії"""
        for folder in [cls.temp_folder, cls.logs_folder]:
            Path(folder).mkdir(exist_ok=True)

    @classmethod
    def _validate_required_settings(cls) -> None:
        """Перевіряє наявність обов'язкових налаштувань"""
        required_settings = [
            ("MONGO_URI", cls.mongo_uri),
            ("AZURE_TENANT_ID", cls.azure_tenant_id),
            ("AZURE_CLIENT_ID", cls.azure_client_id),
            ("AZURE_CLIENT_SECRET", cls.azure_client_secret),
            ("AZURE_STORAGE_ACCOUNT_NAME", cls.azure_storage_account_name),
            ("AZURE_STORAGE_CONTAINER_NAME", cls.azure_storage_container_name),
            ("CVAT_HOST", cls.cvat_host),
            ("CVAT_USERNAME", cls.cvat_username),
            ("CVAT_PASSWORD", cls.cvat_password),
        ]

        missing = []
        for name, value in required_settings:
            if not value:
                missing.append(name)

        if missing:
            raise ValueError(f"Відсутні обов'язкові налаштування: {', '.join(missing)}")

    @classmethod
    def get_azure_account_url(cls) -> str:
        """Повертає URL до Azure Storage Account"""
        return f"https://{cls.azure_storage_account_name}.blob.core.windows.net"

    @classmethod
    def is_local_environment(cls) -> bool:
        """Перевіряє чи це локальне середовище"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        return env in ("development", "dev", "local")

    @classmethod
    def get_environment_name(cls) -> str:
        """Повертає назву поточного середовища"""
        return os.getenv("ENVIRONMENT", "development")


Settings.load_from_env()