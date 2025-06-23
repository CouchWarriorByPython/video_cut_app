from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from backend.models.database import AzureFilePath


class ClipInfoRequest(BaseModel):
    """Clip information in request"""
    id: int
    start_time: str = Field(..., pattern=r'^\d{2}:\d{2}:\d{2}$')
    end_time: str = Field(..., pattern=r'^\d{2}:\d{2}:\d{2}$')


class VideoUploadRequest(BaseModel):
    """Video upload request schema - без where/when"""
    video_urls: List[str] = Field(..., min_length=1, max_items=100)
    download_all_folder: bool = Field(False)

    @field_validator('video_urls')
    def validate_azure_urls(cls, urls: List[str]) -> List[str]:
        validated_urls = []
        for url in urls:
            url = url.strip()
            if not url:
                continue

            if not url.startswith('https://') or '.blob.core.windows.net' not in url:
                raise ValueError(f'URL має бути з Azure Blob Storage: {url}')

            validated_urls.append(url)

        if not validated_urls:
            raise ValueError('Необхідно вказати хоча б один валідний URL')

        return validated_urls

    @field_validator('download_all_folder')
    def validate_folder_mode(cls, v: bool, info: ValidationInfo) -> bool:
        if v and len(info.data.get('video_urls', [])) > 1:
            raise ValueError('При завантаженні папки можна вказати тільки один URL')
        return v


class VideoMetadataRequest(BaseModel):
    """Video metadata in request - додаємо where/when"""
    skip: bool = False
    where: Optional[str] = Field(None, max_length=100)
    when: Optional[str] = Field(None, pattern=r'^\d{8}$')
    uav_type: str = Field("", max_length=100)
    video_content: str = Field("", max_length=100)
    is_urban: bool = False
    has_osd: bool = False
    is_analog: bool = False
    night_video: bool = False
    multiple_streams: bool = False
    has_infantry: bool = False
    has_explosions: bool = False

    @field_validator('where')
    def validate_where(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^[A-Za-z\s\-_]+$', v):
            raise ValueError('Локація може містити тільки англійські літери')
        return v

    @field_validator('uav_type', 'video_content')
    def validate_required_fields(cls, v: str, info: ValidationInfo) -> str:
        if not info.data.get('skip', False) and not v.strip():
            field_names = {
                'uav_type': 'UAV (тип дрона)',
                'video_content': 'Контент відео'
            }
            raise ValueError(f"Поле '{field_names.get(info.field_name, info.field_name)}' є обов'язковим")
        return v.strip()


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