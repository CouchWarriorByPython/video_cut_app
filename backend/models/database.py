from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, UTC


class AzureFilePath(BaseModel):
    """Azure file path structure"""
    account_name: str
    container_name: str
    blob_path: str


class TaskParams(BaseModel):
    """CVAT task parameters"""
    project_id: int
    overlap: int
    segment_size: int
    image_quality: int


class SourceVideo(BaseModel):
    """Source video model based on new schema"""
    azure_file_path: AzureFilePath
    extension: str
    skip_annotation: bool = False
    clips: List[str] = Field(default_factory=list)
    uav_type: Optional[str] = None
    where: Optional[str] = None
    when: Optional[str] = None
    status: str = "queued"
    created_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(sep=" ", timespec="seconds"))
    updated_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(sep=" ", timespec="seconds"))
    duration_sec: Optional[int] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    size_MB: Optional[float] = None
    fps: Optional[int] = None
    video_content: Optional[str] = None
    is_urban: bool = False
    has_osd: bool = False
    is_analog: bool = False
    night_video: bool = False
    multiple_streams: bool = False
    has_infantry: bool = False
    has_explosions: bool = False


class ClipVideo(BaseModel):
    """Clip video model based on new schema"""
    source_video_id: str
    azure_file_path: AzureFilePath
    cvat_task_id: Optional[int] = None
    cvat_task_params: TaskParams
    status: str = "not_annotated"
    extension: str
    duration_sec: int
    start_time_offset_sec: int
    fps: Optional[int] = None
    uav_type: Optional[str] = None
    where: Optional[str] = None
    when: Optional[str] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    size_MB: Optional[float] = None
    created_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(sep=" ", timespec="seconds"))
    updated_at_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(sep=" ", timespec="seconds"))
    cvat_project_id: int