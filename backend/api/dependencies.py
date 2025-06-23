from typing import Dict, Any
from fastapi import Request

from backend.models.api import (
    VideoAnnotationResponse, VideoMetadataResponse,
    CVATProjectParamsResponse, ClipInfoResponse
)
from backend.models.database import AzureFilePath
from backend.database import create_repository


def convert_db_annotation_to_response(annotation: Dict[str, Any]) -> VideoAnnotationResponse:
    """Convert annotation from DB to response model with clip aggregation"""

    azure_file_path_dict = annotation.get("azure_file_path", {})
    if azure_file_path_dict:
        azure_path_obj = AzureFilePath(**azure_file_path_dict)
        filename = azure_path_obj.blob_path.split("/")[-1]
    else:
        azure_path_obj = AzureFilePath(
            account_name="",
            container_name="",
            blob_path=""
        )
        filename = annotation.get("filename", "")

    # Отримуємо кліпи
    clip_repo = create_repository("clip_videos", async_mode=False)
    clips_data = clip_repo.find_all(filter_query={"source_video_id": annotation["_id"]})

    clips = {}
    cvat_params = {}
    metadata = None
    where = None
    when = None

    # Якщо є кліпи - беремо метадані та where/when з першого
    if clips_data:
        first_clip = clips_data[0]
        where = first_clip.get("where")
        when = first_clip.get("when")

        metadata = VideoMetadataResponse(
            skip=annotation.get("skip_annotation", False),
            uav_type=first_clip.get("uav_type", ""),
            video_content=first_clip.get("video_content", ""),
            is_urban=first_clip.get("is_urban", False),
            has_osd=first_clip.get("has_osd", False),
            is_analog=first_clip.get("is_analog", False),
            night_video=first_clip.get("night_video", False),
            multiple_streams=first_clip.get("multiple_streams", False),
            has_infantry=first_clip.get("has_infantry", False),
            has_explosions=first_clip.get("has_explosions", False)
        )

        for clip_data in clips_data:
            project_name = clip_data.get("ml_project", "unknown")

            if project_name not in clips:
                clips[project_name] = []
                cvat_params[project_name] = CVATProjectParamsResponse(
                    **clip_data.get("cvat_task_params", {}),
                    project_id=clip_data.get("cvat_project_id", 0)
                )

            start_time = _seconds_to_time_string(clip_data.get("start_time_offset_sec", 0))
            end_time = _seconds_to_time_string(
                clip_data.get("start_time_offset_sec", 0) + clip_data.get("duration_sec", 0)
            )

            clips[project_name].append(ClipInfoResponse(
                id=len(clips[project_name]),
                start_time=start_time,
                end_time=end_time
            ))
    else:
        # Якщо кліпів немає, але є skip_annotation
        if annotation.get("skip_annotation"):
            metadata = VideoMetadataResponse(skip=True)

    return VideoAnnotationResponse(
        id=annotation["_id"],
        azure_file_path=azure_path_obj,
        filename=filename,
        created_at_utc=annotation.get("created_at_utc", ""),
        updated_at_utc=annotation.get("updated_at_utc", ""),
        when=when,  # З clips
        where=where,  # З clips
        status=annotation.get("status", "unknown"),
        metadata=metadata,
        clips=clips,
        cvat_params=cvat_params
    )


def _seconds_to_time_string(seconds: int) -> str:
    """Convert seconds to HH:MM:SS format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_current_user(request: Request) -> Dict[str, Any]:
    """Get current user from request state"""
    return request.state.user