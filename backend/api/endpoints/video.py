from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from typing import Dict, Any
from backend.models.api import (
    VideoUploadRequest, VideoUploadResponse, VideoStatusResponse
)
from backend.services.video_service import VideoService
from backend.api.dependencies import get_current_user
from backend.utils.logger import get_logger
from backend.services.auth_service import AuthService
from backend.services.azure_service import AzureService
from backend.models.database import AzureFilePath

logger = get_logger(__name__, "api.log")
router = APIRouter(tags=["video"])


@router.post("/upload")
async def upload(data: VideoUploadRequest) -> Dict[str, Any]:
    """Реєстрація відео за Azure URLs - без where/when"""
    video_service = VideoService()

    try:
        if data.download_all_folder:
            # Режим завантаження всіх відео з папки
            folder_url = data.video_urls[0]
            azure_service = AzureService()
            videos_in_folder = azure_service.list_videos_in_folder(folder_url)

            if not videos_in_folder:
                raise HTTPException(
                    status_code=404,
                    detail="Не знайдено відео файлів у вказаній папці"
                )

            # Реєструємо всі знайдені відео
            results = []
            for video_info in videos_in_folder:
                result = video_service.validate_and_register_video(video_info["url"])

                if result["success"]:
                    results.append({
                        "task_id": result.get("task_id"),
                        "azure_file_path": result["azure_file_path"],
                        "filename": result["filename"],
                        "message": result["message"]
                    })

            return {
                "success": True,
                "message": f"Зареєстровано {len(results)} відео з папки",
                "tasks": results
            }

        else:
            # Режим завантаження конкретних URL
            if len(data.video_urls) == 1:
                # Один URL - повертаємо як раніше
                result = video_service.validate_and_register_video(data.video_urls[0])

                if not result["success"]:
                    raise HTTPException(status_code=400, detail=result["error"])

                return VideoUploadResponse(
                    id=result["_id"],
                    azure_file_path=result["azure_file_path"],
                    filename=result["filename"],
                    conversion_task_id=result.get("task_id"),
                    message=result["message"]
                )

            else:
                # Декілька URL
                results = []
                errors = []

                for url in data.video_urls:
                    result = video_service.validate_and_register_video(url)

                    if result["success"]:
                        results.append({
                            "task_id": result.get("task_id"),
                            "azure_file_path": result["azure_file_path"],
                            "filename": result["filename"],
                            "message": result["message"]
                        })
                    else:
                        errors.append(f"{url}: {result['error']}")

                if not results and errors:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Помилки реєстрації всіх відео:\n" + "\n".join(errors)
                    )

                return {
                    "success": True,
                    "message": f"Зареєстровано {len(results)} відео з {len(data.video_urls)}",
                    "tasks": results,
                    "errors": errors if errors else None
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка реєстрації відео: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/get_videos")
async def get_videos_paginated(
        request: Request,
        page: int = Query(1, ge=1, description="Номер сторінки"),
        per_page: int = Query(20, ge=1, le=50, description="Кількість відео на сторінці")
):
    """Отримання пагінованого списку відео з блокуваннями"""
    current_user = get_current_user(request)
    video_service = VideoService()

    result = video_service.get_videos_list_paginated(
        page=page,
        per_page=per_page,
        user_id=current_user["user_id"]
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "success": True,
        "videos": result["videos"],
        "pagination": result["pagination"]
    }


@router.post("/lock_video/{video_id}")
async def lock_video(video_id: str, request: Request):
    """Блокування відео для анотування"""
    current_user = get_current_user(request)
    video_service = VideoService()

    result = video_service.lock_video_for_annotation(
        video_id=video_id,
        user_id=current_user["user_id"],
        user_email=current_user["email"]
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/unlock_video/{video_id}")
async def unlock_video(video_id: str, request: Request):
    """Розблокування відео"""
    current_user = get_current_user(request)
    video_service = VideoService()

    result = video_service.unlock_video_for_annotation(
        video_id=video_id,
        user_id=current_user["user_id"]
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


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