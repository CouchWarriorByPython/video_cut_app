from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class CVATProjectSettings(BaseModel):
    """Модель налаштувань CVAT проєкту"""
    project_name: str = Field(..., pattern="^(motion-det|tracking|mil-hardware|re-id)$")
    project_id: int = Field(..., ge=1, le=1000)
    overlap: int = Field(..., ge=0, le=100)
    segment_size: int = Field(..., ge=50, le=2000)
    image_quality: int = Field(..., ge=1, le=100)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))

    @field_validator('project_id')
    @classmethod
    def validate_project_id_unique(cls, v: int) -> int:
        # Валідація унікальності буде в репозиторії
        return v


class CVATSettingsRequest(BaseModel):
    """Схема для запиту оновлення CVAT налаштувань"""
    project_id: int = Field(..., ge=1, le=1000)
    overlap: int = Field(..., ge=0, le=100)
    segment_size: int = Field(..., ge=50, le=2000)
    image_quality: int = Field(..., ge=1, le=100)


class CVATSettingsResponse(BaseModel):
    """Схема відповіді CVAT налаштувань"""
    id: str
    project_name: str
    project_id: int
    overlap: int
    segment_size: int
    image_quality: int
    created_at: str
    updated_at: str


class AdminStatsResponse(BaseModel):
    """Статистика для адмін панелі"""
    total_users: int
    active_users: int
    total_videos: int
    processing_videos: int
    annotated_videos: int