from typing import Dict, Any

from backend.models.api import (
    VideoAnnotationResponse, VideoMetadataResponse,
    CVATProjectParamsResponse, ClipInfoResponse
)


def convert_db_annotation_to_response(annotation: Dict[str, Any]) -> VideoAnnotationResponse:
    """Конвертує анотацію з БД у response модель"""
    metadata = None
    if annotation.get("metadata"):
        metadata = VideoMetadataResponse(**annotation["metadata"])

    clips = {}
    if annotation.get("clips"):
        for project, project_clips in annotation["clips"].items():
            clips[project] = [ClipInfoResponse(**clip) for clip in project_clips]

    cvat_params = {}
    if annotation.get("cvat_params"):
        for project, params in annotation["cvat_params"].items():
            cvat_params[project] = CVATProjectParamsResponse(**params)

    return VideoAnnotationResponse(
        id=annotation["_id"],
        azure_link=annotation["azure_link"],
        filename=annotation["filename"],
        created_at=annotation["created_at"],
        updated_at=annotation["updated_at"],
        when=annotation.get("when"),
        where=annotation.get("where"),
        status=annotation["status"],
        metadata=metadata,
        clips=clips,
        cvat_params=cvat_params
    )