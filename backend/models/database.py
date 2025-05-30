from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ClipInfo(BaseModel):
    """Інформація про відрізок відео"""
    id: int
    start_time: str
    end_time: str


class VideoMetadata(BaseModel):
    """Метадані відео"""
    skip: bool = False
    uav_type: str = ""
    video_content: str = ""
    is_urban: bool = False
    has_osd: bool = False
    is_analog: bool = False
    night_video: bool = False
    multiple_streams: bool = False
    has_infantry: bool = False
    has_explosions: bool = False


class CVATProjectParams(BaseModel):
    """Параметри проєкту CVAT"""
    project_id: int
    overlap: int
    segment_size: int
    image_quality: int


class SourceVideoAnnotation(BaseModel):
    """Модель анотації соурс відео"""
    azure_link: str
    filename: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    when: Optional[str] = None
    where: Optional[str] = None
    status: str = "not_annotated"
    metadata: Optional[VideoMetadata] = None
    clips: Dict[str, List[ClipInfo]] = Field(default_factory=dict)
    cvat_params: Dict[str, CVATProjectParams] = Field(default_factory=dict)


class VideoClipRecord(BaseModel):
    """Модель запису відео кліпу"""
    source_id: str
    project: str
    clip_id: int
    extension: str = "mp4"
    cvat_task_id: Optional[str] = None
    status: str = "not_annotated"
    azure_link: str
    fps: Optional[float] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))