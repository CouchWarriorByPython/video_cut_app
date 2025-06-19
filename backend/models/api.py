from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from backend.models.database import AzureFilePath


class ClipInfoRequest(BaseModel):
    """Clip information in request"""
    id: int
    start_time: str = Field(..., pattern=r'^\d{2}:\d{2}:\d{2}$')
    end_time: str = Field(..., pattern=r'^\d{2}:\d{2}:\d{2}$')


class VideoMetadataRequest(BaseModel):
    """Video metadata in request"""
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
    def validate_required_fields(cls, v: str, info: ValidationInfo) -> str:
        if not info.data.get('skip', False) and not v.strip():
            field_names = {
                'uav_type': 'UAV (тип дрона)',
                'video_content': 'Контент відео'
            }
            raise ValueError(f"Поле '{field_names.get(info.field_name, info.field_name)}' є обов'язковим")
        return v.strip()

    @field_validator('video_content')
    def validate_video_content_options(cls, v: str) -> str:
        if not v.strip():
            return v

        valid_options = ['recon', 'interception', 'bombing', 'strike', 'panoramic', 'other']
        if v.strip() not in valid_options:
            raise ValueError(f"Недопустимий тип контенту. Допустимі варіанти: {', '.join(valid_options)}")
        return v.strip()


class VideoUploadRequest(BaseModel):
    """Video upload request schema"""
    video_url: str = Field(..., min_length=1, max_length=2048)
    where: Optional[str] = Field(None, max_length=100)
    when: Optional[str] = Field(None, pattern=r'^\d{8}$')

    @field_validator('video_url')
    def validate_azure_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith('https://') or '.blob.core.windows.net' not in v:
            raise ValueError('URL має бути з Azure Blob Storage')

        supported_extensions = ['.mp4', '.avi', '.mov', '.mkv']
        if not any(v.lower().endswith(ext) for ext in supported_extensions):
            raise ValueError(f'Підтримувані формати відео: {", ".join(supported_extensions)}')

        return v


class SaveFragmentsRequest(BaseModel):
    """Save fragments request schema"""
    azure_file_path: AzureFilePath = Field(...)
    data: Dict[str, Any] = Field(...)


class BaseResponse(BaseModel):
    """Base response schema"""
    success: bool = True


class ErrorResponse(BaseResponse):
    """Error response schema"""
    success: bool = False
    message: str
    error: Optional[str] = None


class VideoUploadResponse(BaseResponse):
    """Video upload response"""
    id: str
    azure_file_path: AzureFilePath
    filename: str
    conversion_task_id: Optional[str] = None
    message: str


class VideoStatusResponse(BaseResponse):
    """Video status response"""
    status: str
    filename: str
    ready_for_annotation: bool


class SaveFragmentsResponse(BaseResponse):
    """Save fragments response"""
    id: str
    task_id: Optional[str] = None
    message: str


class ClipInfoResponse(BaseModel):
    """Clip information in response"""
    id: int
    start_time: str
    end_time: str


class VideoMetadataResponse(BaseModel):
    """Video metadata in response"""
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
    """CVAT project parameters in response"""
    project_id: int
    overlap: int
    segment_size: int
    image_quality: int


class VideoAnnotationResponse(BaseModel):
    """Video annotation response"""
    id: str
    azure_file_path: AzureFilePath
    filename: str
    created_at_utc: str
    updated_at_utc: str
    when: Optional[str] = None
    where: Optional[str] = None
    status: str
    metadata: Optional[VideoMetadataResponse] = None
    clips: Dict[str, List[ClipInfoResponse]] = Field(default_factory=dict)
    cvat_params: Dict[str, CVATProjectParamsResponse] = Field(default_factory=dict)


class VideoListResponse(BaseResponse):
    """Video list response"""
    videos: List[VideoAnnotationResponse]


class GetAnnotationResponse(BaseResponse):
    """Get annotation response"""
    annotation: Optional[VideoAnnotationResponse] = None