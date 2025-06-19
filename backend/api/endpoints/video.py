from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.models.api import (
    VideoUploadRequest, VideoUploadResponse,
    VideoListResponse, VideoStatusResponse
)
from backend.services.video_service import VideoService
from backend.api.dependencies import convert_db_annotation_to_response
from backend.utils.logger import get_logger
from backend.services.auth_service import AuthService
from backend.models.database import AzureFilePath

logger = get_logger(__name__, "api.log")
router = APIRouter(tags=["video"])


@router.post("/upload", response_model=VideoUploadResponse)
async def upload(data: VideoUploadRequest) -> VideoUploadResponse:
    """Реєстрація відео за Azure URL з асинхронним завантаженням та конвертацією"""
    video_service = VideoService()

    result = video_service.validate_and_register_video(
        data.video_url, data.where, data.when
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return VideoUploadResponse(
        id=result["_id"],
        azure_file_path=result["azure_file_path"],
        filename=result["filename"],
        conversion_task_id=result.get("task_id"),
        message=result["message"]
    )


@router.get("/task_status/{task_id}")
async def get_task_status(task_id: str):
    """Отримання статусу виконання Celery задачі"""
    video_service = VideoService()

    result = video_service.get_task_status(task_id)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "status": result["status"],
        "progress": result["progress"],
        "stage": result["stage"],
        "message": result["message"],
        "result": result.get("result")
    }


@router.get("/video_status", response_model=VideoStatusResponse)
async def get_video_status(
    account_name: str = Query(...),
    container_name: str = Query(...),
    blob_path: str = Query(...)
) -> VideoStatusResponse:
    """Отримання статусу обробки відео"""
    video_service = VideoService()

    azure_path = AzureFilePath(
        account_name=account_name,
        container_name=container_name,
        blob_path=blob_path
    )

    result = video_service.get_video_status(azure_path)

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


@router.get("/get_videos", response_model=VideoListResponse)
async def get_videos() -> VideoListResponse:
    """Отримання списку відео які ще не анотовані"""
    video_service = VideoService()

    result = video_service.get_videos_list()

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    videos = [convert_db_annotation_to_response(video) for video in result["videos"]]
    return VideoListResponse(videos=videos)


@router.get("/get_video")
async def get_video(
    account_name: str = Query(...),
    container_name: str = Query(...),
    blob_path: str = Query(...),
    token: str = Query(...)
) -> FileResponse:
    """Відображає локальне відео для анотування з перевіркою токена"""

    auth_service = AuthService()
    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Невалідний токен")

    allowed_roles = ["annotator", "admin", "super_admin"]
    if payload.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Недостатньо прав доступу")

    video_service = VideoService()

    azure_path = AzureFilePath(
        account_name=account_name,
        container_name=container_name,
        blob_path=blob_path
    )

    local_path = video_service.get_video_for_streaming(azure_path)

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