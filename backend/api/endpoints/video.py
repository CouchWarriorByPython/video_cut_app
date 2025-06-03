from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from backend.models.api import (
    VideoUploadRequest, VideoUploadResponse, ErrorResponse,
    VideoListResponse, VideoStatusResponse
)
from backend.services.video_service import VideoService
from backend.api.dependencies import convert_db_annotation_to_response
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")
router = APIRouter(tags=["video"])


@router.post("/upload",
             response_model=VideoUploadResponse,
             responses={
                 400: {"model": ErrorResponse},
                 500: {"model": ErrorResponse}
             })
async def upload(data: VideoUploadRequest) -> VideoUploadResponse:
    """Реєстрація відео за Azure URL з локальним завантаженням"""
    video_service = VideoService()

    result = video_service.validate_and_register_video(
        data.video_url, data.where, data.when
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return VideoUploadResponse(
        id=result["_id"],
        azure_link=result["azure_link"],
        filename=result["filename"],
        conversion_task_id=result.get("conversion_task_id"),
        message=result["message"]
    )


@router.get("/video_status",
            response_model=VideoStatusResponse,
            responses={
                404: {"model": ErrorResponse},
                500: {"model": ErrorResponse}
            })
async def get_video_status(azure_link: str) -> VideoStatusResponse:
    """Отримання статусу обробки відео"""
    video_service = VideoService()

    result = video_service.get_video_status(azure_link)

    if not result["success"]:
        if "не знайдено" in result["error"]:
            raise HTTPException(status_code=404, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    return VideoStatusResponse(
        status=result["status"],
        filename=result["filename"],
        ready_for_annotation=result["ready_for_annotation"]
    )


@router.get("/get_videos",
            response_model=VideoListResponse,
            responses={500: {"model": ErrorResponse}})
async def get_videos() -> VideoListResponse:
    """Отримання списку відео які ще не анотовані"""
    video_service = VideoService()

    result = video_service.get_videos_list()

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    videos = [convert_db_annotation_to_response(video) for video in result["videos"]]
    return VideoListResponse(videos=videos)


@router.get("/get_video")
async def get_video(azure_link: str) -> FileResponse:
    """Відображає локальне відео для анотування"""
    video_service = VideoService()

    local_path = video_service.get_video_for_streaming(azure_link)

    if not local_path:
        raise HTTPException(status_code=404, detail="Відео не знайдено або ще не готове")

    import os
    filename = os.path.basename(local_path)

    return FileResponse(
        path=local_path,
        media_type="video/mp4",
        filename=filename,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Content-Type": "video/mp4"
        }
    )


@router.get("/favicon.ico")
async def serve_favicon():
    """Іконка сайту - заглушка"""
    return Response(status_code=204)