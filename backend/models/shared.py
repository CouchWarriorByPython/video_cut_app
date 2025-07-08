from enum import Enum
from typing import Annotated
from pydantic import BaseModel, Field, field_validator
from backend.config.settings import get_settings

settings = get_settings()


class VideoStatus(str, Enum):
    DOWNLOADING = "downloading"
    NOT_ANNOTATED = "not_annotated"
    IN_PROGRESS = "in_progress"
    PROCESSING_CLIPS = "processing_clips"
    ANNOTATED = "annotated"
    DOWNLOAD_ERROR = "download_error"
    ANNOTATION_ERROR = "annotation_error"


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    ANNOTATOR = "annotator"


class MLProject(str, Enum):
    MOTION_DETECTION = "motion_detection"
    MILITARY_TARGETS_MOVING = "military_targets_detection_and_tracking_moving"
    MILITARY_TARGETS_STATIC = "military_targets_detection_and_tracking_static"
    RE_ID = "re_id"


class AzureFilePath(BaseModel):
    """Azure file path with validation"""
    account_name: Annotated[str, Field(pattern=r'^[a-z0-9\-_]+$', max_length=100)]
    container_name: Annotated[str, Field(pattern=r'^[a-z0-9\-_]+$', max_length=100)]
    blob_path: Annotated[str, Field(min_length=1)]

    @field_validator('account_name')
    def validate_account_name(cls, v: str) -> str:
        if v != settings.azure_storage_account_name:
            raise ValueError(f'Account name must be {settings.azure_storage_account_name}')
        return v

    @field_validator('blob_path')
    def validate_blob_path(cls, v: str) -> str:
        if v.startswith('/') or v.endswith('/'):
            raise ValueError('Blob path should not start or end with /')
        return v


class CVATSettings(BaseModel):
    """CVAT project settings - unified model"""
    project_name: MLProject
    project_id: Annotated[int, Field(ge=1, le=1000, description="ID проєкту CVAT (від 1 до 1000)")]
    overlap: Annotated[int, Field(ge=0, le=100, description="Перекриття сегментів у відсотках (від 0 до 100)")]
    segment_size: Annotated[int, Field(ge=50, le=2000, description="Розмір сегмента (від 50 до 2000)")]
    image_quality: Annotated[int, Field(ge=1, le=100, description="Якість зображення у відсотках (від 1 до 100)")]

    @field_validator('project_id')
    def validate_project_id(cls, v: int) -> int:
        if not (1 <= v <= 1000):
            raise ValueError("Project ID повинен бути від 1 до 1000")
        return v

    @field_validator('overlap')
    def validate_overlap(cls, v: int) -> int:
        if not (0 <= v <= 100):
            raise ValueError("Overlap повинен бути від 0 до 100 відсотків")
        return v

    @field_validator('segment_size')
    def validate_segment_size(cls, v: int) -> int:
        if not (50 <= v <= 2000):
            raise ValueError("Segment size повинен бути від 50 до 2000")
        return v

    @field_validator('image_quality')
    def validate_image_quality(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("Image quality повинна бути від 1 до 100 відсотків")
        return v
