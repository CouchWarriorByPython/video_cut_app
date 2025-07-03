from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Централізовані налаштування програми"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # MongoDB - обов'язкові
    mongo_uri: str
    mongo_db: str = Field(default="video_annotator")

    # Redis & Celery - дефолти для локальної розробки
    redis_url: str = Field(default="redis://redis:6379/0")
    celery_broker_url: str = Field(default="redis://redis:6379/0")
    celery_result_backend: str = Field(default="redis://redis:6379/0")

    # Azure - обов'язкові лише account і container
    azure_storage_account_name: str
    azure_storage_container_name: str
    azure_input_folder_path: str = Field(default="input/")
    azure_output_folder_path: str = Field(default="output/")

    # Azure credentials - опціональні для підтримки az login
    azure_tenant_id: Optional[str] = Field(default=None)
    azure_client_id: Optional[str] = Field(default=None)
    azure_client_secret: Optional[str] = Field(default=None)
    azure_storage_connection_string: Optional[str] = Field(default=None)

    # CVAT - обов'язкові
    cvat_host: str
    cvat_port: int = Field(default=8080)
    cvat_username: str
    cvat_password: str

    # Paths - дефолти для структури проєкту
    temp_folder: str = Field(default="temp")
    logs_folder: str = Field(default="logs")

    # Logging - розумні дефолти
    log_level: str = Field(default="INFO")
    log_max_bytes: int = Field(default=10485760)  # 10MB
    log_backup_count: int = Field(default=5)

    # FFmpeg
    ffmpeg_log_level: str = Field(default="error")

    # FastAPI
    fast_api_host: str = Field(default="0.0.0.0")
    fast_api_port: int = Field(default=8000)
    reload: bool = Field(default=False)

    # Azure processing - технічні дефолти
    azure_download_chunk_size: int = Field(default=16777216)  # 16MB
    azure_max_concurrency: int = Field(default=4)

    # Video conversion - технічні дефолти
    video_conversion_preset: str = Field(default="fast")
    video_conversion_crf: int = Field(default=23)
    enable_hardware_acceleration: bool = Field(default=False)
    skip_conversion_for_compatible: bool = Field(default=True)

    # JWT - обов'язковий secret_key
    secret_key: str = Field(alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_minutes: int = Field(default=10080)  # 7 days

    # Super Admins - обов'язкові
    super_admin_email_1: Optional[str] = Field(default=None)
    super_admin_password_1: Optional[str] = Field(default=None)
    super_admin_email_2: Optional[str] = Field(default=None)
    super_admin_password_2: Optional[str] = Field(default=None)

    # Environment
    environment: str = Field(default="development")

    @field_validator("reload", mode="before")
    @classmethod
    def parse_bool(cls, v: str | bool) -> bool:
        """Парсинг булевих значень з рядків"""
        if isinstance(v, bool):
            return v
        return v.lower() in ("true", "1", "yes")

    @field_validator("enable_hardware_acceleration", "skip_conversion_for_compatible", mode="before")
    @classmethod
    def parse_bool_fields(cls, v: str | bool) -> bool:
        """Парсинг булевих полів"""
        if isinstance(v, bool):
            return v
        return v.lower() in ("true", "1", "yes")

    @computed_field
    @property
    def azure_account_url(self) -> str:
        """URL до Azure Storage Account"""
        return f"https://{self.azure_storage_account_name}.blob.core.windows.net"

    @computed_field
    @property
    def is_local_environment(self) -> bool:
        """Перевіряє чи це локальне середовище"""
        return self.environment.lower() in ("development", "dev", "local")

    @computed_field
    @property
    def mongo_db_name(self) -> str:
        """Для зворотної сумісності"""
        return self.mongo_db

    @computed_field
    @property
    def has_azure_credentials(self) -> bool:
        """Перевіряє наявність Azure service principal credentials"""
        return bool(self.azure_tenant_id and self.azure_client_id and self.azure_client_secret)

    def create_directories(self) -> None:
        """Створює необхідні директорії"""
        for folder in [self.temp_folder, self.logs_folder]:
            Path(folder).mkdir(exist_ok=True)

    def model_post_init(self, __context) -> None:
        """Ініціалізація після створення моделі"""
        self.create_directories()


@lru_cache
def get_settings() -> Settings:
    """Повертає singleton інстанс Settings"""
    return Settings()
