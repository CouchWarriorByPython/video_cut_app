from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ValidationInfo


class ClipInfoRequest(BaseModel):
    """Схема для інформації про кліп в запиті"""
    id: int
    start_time: str = Field(..., pattern=r'^\d{2}:\d{2}:\d{2}$')
    end_time: str = Field(..., pattern=r'^\d{2}:\d{2}:\d{2}$')


class VideoMetadataRequest(BaseModel):
    """Схема для метаданих відео в запиті"""
    skip: bool = False
    uav_type: str = Field("", max_length=100)
    video_content: str = Field("", max_length=100)
    is_urban: bool = False
    has_osd: bool = False
    is_analog: bool = False
    night_video: bool = False
    multiple_streams: bool = False
    has_infantry: bool = False
    has_explosions: bool = False

    @field_validator('uav_type', 'video_content')
    @classmethod
    def validate_required_fields(cls, v: str, info: ValidationInfo) -> str:
        if not info.data.get('skip', False) and not v.strip():
            field_names = {
                'uav_type': 'UAV (тип дрона)',
                'video_content': 'Контент відео'
            }
            raise ValueError(f"Поле '{field_names.get(info.field_name, info.field_name)}' є обов'язковим")
        return v.strip()


class VideoUploadRequest(BaseModel):
    """Схема для запиту завантаження відео"""
    video_url: str = Field(..., min_length=1, max_length=2048)
    where: Optional[str] = Field(None, max_length=100)
    when: Optional[str] = Field(None, pattern=r'^\d{8}$')

    @field_validator('video_url')
    @classmethod
    def validate_azure_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith('https://') or '.blob.core.windows.net' not in v:
            raise ValueError('URL має бути з Azure Blob Storage')
        return v

    @field_validator('where')
    @classmethod
    def validate_where(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.replace(' ', '').replace('-', '').replace('_', '').isalpha():
            raise ValueError('Локація може містити тільки англійські літери, пробіли, дефіси та підкреслення')
        return v.strip() if v else None


class SaveFragmentsRequest(BaseModel):
    """Схема для запиту збереження фрагментів"""
    azure_link: str = Field(..., min_length=1)
    data: Dict[str, Any] = Field(...)


class BaseResponse(BaseModel):
    """Базова схема відповіді"""
    success: bool = True


class ErrorResponse(BaseResponse):
    """Схема для відповіді з помилкою"""
    success: bool = False
    message: str
    error: Optional[str] = None


class VideoUploadResponse(BaseResponse):
    """Схема відповіді для завантаження відео"""
    _id: str
    azure_link: str
    filename: str
    message: str


class SaveFragmentsResponse(BaseResponse):
    """Схема відповіді для збереження фрагментів"""
    _id: str
    task_id: Optional[str] = None
    message: str


class ClipInfoResponse(BaseModel):
    """Схема для інформації про кліп у відповіді"""
    id: int
    start_time: str
    end_time: str


class VideoMetadataResponse(BaseModel):
    """Схема для метаданих відео у відповіді"""
    skip: bool
    uav_type: str
    video_content: str
    is_urban: bool
    has_osd: bool
    is_analog: bool
    night_video: bool
    multiple_streams: bool
    has_infantry: bool
    has_explosions: bool


class CVATProjectParamsResponse(BaseModel):
    """Схема для параметрів CVAT проєкту у відповіді"""
    project_id: int
    overlap: int
    segment_size: int
    image_quality: int


class VideoAnnotationResponse(BaseModel):
    """Схема для анотації відео у відповіді"""
    _id: str
    azure_link: str
    filename: str
    size: int
    content_type: str
    created_at: str
    updated_at: str
    when: Optional[str] = None
    where: Optional[str] = None
    status: str
    metadata: Optional[VideoMetadataResponse] = None
    clips: Dict[str, List[ClipInfoResponse]] = Field(default_factory=dict)
    cvat_params: Dict[str, CVATProjectParamsResponse] = Field(default_factory=dict)


class VideoListResponse(BaseResponse):
    """Схема відповіді для списку відео"""
    videos: List[VideoAnnotationResponse]


class GetAnnotationResponse(BaseResponse):
    """Схема відповіді для отримання анотації"""
    annotation: Optional[VideoAnnotationResponse] = None


class ValidationErrorResponse(BaseModel):
    """Схема для відповіді з помилкою валідації"""
    success: bool = False
    message: str
    errors: List[Dict[str, Any]]