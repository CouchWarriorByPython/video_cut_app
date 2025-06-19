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

    metadata = None
    if any(key in annotation for key in
           ["skip_annotation", "uav_type", "video_content", "is_urban", "has_osd", "is_analog", "night_video",
            "multiple_streams", "has_infantry", "has_explosions"]):
        # Правильна обробка None значень з БД
        uav_type = annotation.get("uav_type") or ""
        video_content = annotation.get("video_content") or ""

        metadata = VideoMetadataResponse(
            skip=annotation.get("skip_annotation", False),
            uav_type=uav_type,
            video_content=video_content,
            is_urban=annotation.get("is_urban", False),
            has_osd=annotation.get("has_osd", False),
            is_analog=annotation.get("is_analog", False),
            night_video=annotation.get("night_video", False),
            multiple_streams=annotation.get("multiple_streams", False),
            has_infantry=annotation.get("has_infantry", False),
            has_explosions=annotation.get("has_explosions", False)
        )

    clips = {}
    cvat_params = {}

    clip_repo = create_repository("clip_videos", async_mode=False)
    clips_data = clip_repo.find_all(filter_query={"source_video_id": annotation["_id"]})

    project_mapping = {
        5: "motion-det",
        6: "tracking",
        7: "mil-hardware",
        8: "re-id"
    }

    for clip_data in clips_data:
        project_id = clip_data.get("cvat_project_id")
        project_name = project_mapping.get(project_id, "unknown")

        if project_name not in clips:
            clips[project_name] = []
            cvat_params[project_name] = CVATProjectParamsResponse(**clip_data.get("cvat_task_params", {}))

        start_time = _seconds_to_time_string(clip_data.get("start_time_offset_sec", 0))
        end_time = _seconds_to_time_string(
            clip_data.get("start_time_offset_sec", 0) + clip_data.get("duration_sec", 0)
        )

        clips[project_name].append(ClipInfoResponse(
            id=len(clips[project_name]),
            start_time=start_time,
            end_time=end_time
        ))

    return VideoAnnotationResponse(
        id=annotation["_id"],
        azure_file_path=azure_path_obj,
        filename=filename,
        created_at_utc=annotation.get("created_at_utc", annotation.get("created_at_utc", "")),
        updated_at_utc=annotation.get("updated_at_utc", annotation.get("updated_at_utc", "")),
        when=annotation.get("when"),
        where=annotation.get("where"),
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