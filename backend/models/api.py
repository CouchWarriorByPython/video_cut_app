from __future__ import annotations

from typing import Dict, List, Optional, Any, Annotated
from pydantic import (
    BaseModel, Field, field_validator, model_validator,
    EmailStr, HttpUrl, conint, constr, ConfigDict
)
from backend.models.shared import AzureFilePath, UserRole, MLProject, VideoStatus, CVATSettings


class PasswordStr(constr(min_length=8, max_length=128)):
    """Password with validation"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class AzureUrl(HttpUrl):
    """Azure Storage URL validator"""

    @field_validator('*', mode='after')
    def validate_azure_url(cls, v: HttpUrl) -> HttpUrl:
        if '.blob.core.windows.net' not in str(v):
            raise ValueError('URL must be from Azure Blob Storage')
        return v


class CurrentUser(BaseModel):
    """Current authenticated user data"""
    user_id: str
    email: EmailStr
    role: UserRole
    is_active: bool = True

    @classmethod
    def from_token_payload(cls, payload: Dict[str, Any]) -> CurrentUser:
        return cls(
            user_id=payload["user_id"],
            email=payload["sub"],
            role=payload["role"],
            is_active=True
        )

    @classmethod
    def from_document(cls, user: Any) -> CurrentUser:
        return cls(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            is_active=user.is_active
        )


class TokenPayload(BaseModel):
    """JWT Token payload structure"""
    sub: EmailStr
    user_id: str
    role: UserRole
    exp: int
    type: constr(pattern='^(access|refresh)$')


class ClipInfoRequest(BaseModel):
    """Clip information in request"""
    id: conint(ge=0)
    start_time: Annotated[str, Field(pattern=r'^\d{2}:\d{2}:\d{2}$')]
    end_time: Annotated[str, Field(pattern=r'^\d{2}:\d{2}:\d{2}$')]

    @model_validator(mode='after')
    def validate_time_order(self) -> ClipInfoRequest:
        start_seconds = self._time_to_seconds(self.start_time)
        end_seconds = self._time_to_seconds(self.end_time)

        if end_seconds <= start_seconds:
            raise ValueError('End time must be after start time')

        if end_seconds - start_seconds < 1:
            raise ValueError('Clip duration must be at least 1 second')

        return self

    @staticmethod
    def _time_to_seconds(time_str: str) -> int:
        parts = time_str.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


class VideoUploadRequest(BaseModel):
    """Video upload request schema"""
    video_urls: List[Annotated[AzureUrl, Field(description="Azure Blob Storage URLs")]] = Field(
        ..., min_length=1, max_length=100
    )
    download_all_folder: bool = False

    @model_validator(mode='after')
    def validate_folder_mode(self) -> VideoUploadRequest:
        if self.download_all_folder and len(self.video_urls) > 1:
            raise ValueError('Only one URL allowed when downloading entire folder')
        return self


class VideoMetadataRequest(BaseModel):
    """Video metadata in request"""
    skip: bool = False
    where: Optional[Annotated[str, Field(pattern=r'^[A-Za-z\s\-_]+$', max_length=100)]] = None
    when: Optional[Annotated[str, Field(pattern=r'^\d{8}$')]] = None
    uav_type: constr(max_length=100) = ""
    video_content: constr(max_length=100) = ""
    is_urban: bool = False
    has_osd: bool = False
    is_analog: bool = False
    night_video: bool = False
    multiple_streams: bool = False
    has_infantry: bool = False
    has_explosions: bool = False

    @model_validator(mode='after')
    def validate_required_fields(self) -> VideoMetadataRequest:
        if not self.skip:
            if not self.uav_type.strip():
                raise ValueError("UAV type is required when skip is False")
            if not self.video_content.strip():
                raise ValueError("Video content is required when skip is False")
        return self


class SaveFragmentsRequest(BaseModel):
    """Save fragments request schema"""
    azure_file_path: AzureFilePath
    data: Dict[str, Any]

    @field_validator('data')
    def validate_data_structure(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if 'metadata' not in v:
            raise ValueError('Data must contain metadata')
        if 'clips' not in v:
            raise ValueError('Data must contain clips')

        clips = v.get('clips', {})
        for project, project_clips in clips.items():
            if project not in [p.value for p in MLProject]:
                raise ValueError(f'Invalid project: {project}')

            if not isinstance(project_clips, list):
                raise ValueError(f'Clips for {project} must be a list')

        return v


class PaginationRequest(BaseModel):
    """Pagination parameters"""
    page: conint(ge=1) = 1
    per_page: conint(ge=1, le=100) = 20


class UserCreate(BaseModel):
    """User creation request"""
    email: EmailStr
    password: PasswordStr
    role: str

    @field_validator('role')
    def validate_role(cls, v: str) -> str:
        allowed_roles = [UserRole.ADMIN.value, UserRole.ANNOTATOR.value]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class UserUpdateRequest(BaseModel):
    """User update request"""
    email: Optional[EmailStr] = None
    password: Optional[PasswordStr] = None
    role: Optional[str] = None

    @field_validator('role')
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed_roles = [UserRole.ADMIN.value, UserRole.ANNOTATOR.value]
            if v not in allowed_roles:
                raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v

    @model_validator(mode='after')
    def validate_at_least_one_field(self) -> UserUpdateRequest:
        if not any([self.email, self.password, self.role]):
            raise ValueError('At least one field must be provided for update')
        return self


class LoginRequest(BaseModel):
    """Login request"""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: constr(min_length=10)


class BaseResponse(BaseModel):
    """Base response schema"""
    model_config = ConfigDict(from_attributes=True)
    success: bool = True


class ErrorResponse(BaseResponse):
    """Error response schema"""
    success: bool = False
    message: str
    error: Optional[str] = None
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class VideoUploadResponse(BaseResponse):
    """Video upload response"""
    id: str
    azure_file_path: Optional[AzureFilePath] = None
    filename: str
    conversion_task_id: Optional[str] = None
    message: str
    batch_results: Optional[Dict[str, List[Dict[str, Any]]]] = None


class VideoInfoResponse(BaseModel):
    """Video info in list"""
    id: str
    azure_file_path: AzureFilePath
    filename: str
    status: VideoStatus
    created_at_utc: str
    where: Optional[str] = None
    when: Optional[str] = None
    uav_type: Optional[str] = None
    duration_sec: Optional[int] = None
    lock_status: Dict[str, Any]
    can_start_work: bool


class PaginationInfo(BaseModel):
    """Pagination info"""
    current_page: int
    per_page: int
    total_count: int
    total_pages: int
    has_next: bool
    has_prev: bool


class VideoListResponse(BaseResponse):
    """Video list response"""
    videos: List[VideoInfoResponse]
    pagination: PaginationInfo


class LockVideoResponse(BaseResponse):
    """Lock video response"""
    message: str
    expires_at: Optional[str] = None


class VideoStatusResponse(BaseResponse):
    """Video status response"""
    status: VideoStatus
    filename: str
    ready_for_annotation: bool


class SaveFragmentsResponse(BaseResponse):
    """Save fragments response"""
    id: str
    task_id: Optional[str] = None
    message: str


class ClipInfoResponse(BaseModel):
    """Clip info in response"""
    id: int
    start_time: Annotated[str, Field(pattern=r'^\d{2}:\d{2}:\d{2}$')]
    end_time: Annotated[str, Field(pattern=r'^\d{2}:\d{2}:\d{2}$')]


class VideoMetadataResponse(BaseModel):
    """Video metadata in response"""
    skip: bool
    where: Optional[str] = None
    when: Optional[str] = None
    uav_type: str
    video_content: str
    is_urban: bool
    has_osd: bool
    is_analog: bool
    night_video: bool
    multiple_streams: bool
    has_infantry: bool
    has_explosions: bool


class AdminStatsResponse(BaseModel):
    """Admin statistics response"""
    total_users: int
    active_users: int
    total_videos: int
    processing_videos: int
    annotated_videos: int


class VideoAnnotationResponse(BaseModel):
    """Video annotation response"""
    id: str
    azure_file_path: AzureFilePath
    filename: str
    created_at_utc: str
    updated_at_utc: str
    status: VideoStatus
    metadata: Optional[VideoMetadataResponse] = None
    clips: Dict[str, List[ClipInfoResponse]] = Field(default_factory=dict)
    cvat_settings: Dict[str, CVATSettings] = Field(default_factory=dict)


class GetAnnotationResponse(BaseResponse):
    """Get annotation response"""
    annotation: Optional[VideoAnnotationResponse] = None


class UserResponse(BaseModel):
    """User response"""
    id: str
    email: EmailStr
    role: UserRole
    created_at_utc: str
    is_active: bool


class Token(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreateResponse(BaseResponse):
    """User creation response"""
    message: str
    user_id: Optional[str] = None


class UserDeleteResponse(BaseResponse):
    """User deletion response"""
    message: str