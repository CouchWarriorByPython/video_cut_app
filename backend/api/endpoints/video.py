from typing import Annotated, Dict
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse

from backend.models.api import (
    VideoUploadRequest, VideoUploadResponse, VideoStatusResponse,
    VideoListResponse, LockVideoResponse, ErrorResponse
)
from backend.services.video_service import VideoService
from backend.services.auth_service import AuthService
from backend.api.dependencies import get_current_user, get_azure_path_from_query, get_pagination_params

from backend.models.shared import AzureFilePath

router = APIRouter(prefix="/video", tags=["video"])


@router.post(
    "/upload",
    response_model=VideoUploadResponse,
    summary="Завантажити відео з Azure",
    description="Реєструє відео з Azure URLs для асинхронної обробки. Підтримує завантаження окремих файлів або всієї папки",
    responses={
        400: {"model": ErrorResponse, "description": "Невалідні дані або помилка бізнес-логіки"},
        422: {"model": ErrorResponse, "description": "Помилка валідації даних"}
    }
)
async def upload_video(
        data: VideoUploadRequest,
        _current_user: Annotated[dict, Depends(get_current_user)],
        video_service: Annotated[VideoService, Depends(VideoService)]
) -> VideoUploadResponse:
    """Реєстрація відео з Azure URLs"""
    video_urls = [str(url) for url in data.video_urls]

    if data.download_all_folder:
        return video_service.register_videos_from_folder(video_urls[0])
    elif len(video_urls) == 1:
        return video_service.register_single_video(video_urls[0])
    else:
        return video_service.register_multiple_videos(video_urls)


@router.get(
    "/task/{task_id}/status",
    summary="Статус завдання обробки",
    description="Отримує статус виконання Celery завдання для відстеження прогресу завантаження та конвертації відео",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка отримання статусу завдання"}
    }
)
async def get_task_status(
        task_id: str,
        _current_user: Annotated[dict, Depends(get_current_user)],
        video_service: Annotated[VideoService, Depends(VideoService)]
):
    """Статус Celery завдання"""
    return video_service.get_task_status(task_id)


@router.get(
    "/status",
    response_model=VideoStatusResponse,
    summary="Статус відео",
    description="Перевіряє статус обробки відео за його Azure шляхом",
    responses={
        404: {"model": ErrorResponse, "description": "Відео не знайдено"},
        422: {"model": ErrorResponse, "description": "Невалідні параметри Azure path"}
    }
)
async def get_video_status(
        _current_user: Annotated[dict, Depends(get_current_user)],
        video_service: Annotated[VideoService, Depends(VideoService)],
        azure_path: Annotated[AzureFilePath, Depends(get_azure_path_from_query)]
) -> VideoStatusResponse:
    """Статус обробки відео"""
    return video_service.get_video_status(azure_path)


@router.get(
    "/list",
    response_model=VideoListResponse,
    summary="Список відео",
    description="Повертає пагінований список відео з інформацією про блокування та можливість роботи",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка отримання списку відео"}
    }
)
async def get_videos_list(
        current_user: Annotated[dict, Depends(get_current_user)],
        video_service: Annotated[VideoService, Depends(VideoService)],
        pagination: Annotated[Dict[str, int], Depends(get_pagination_params)]
) -> VideoListResponse:
    """Пагінований список відео"""
    return video_service.get_videos_list_paginated(
        page=pagination["page"],
        per_page=pagination["per_page"],
        user_id=current_user["user_id"]
    )


@router.post(
    "/{video_id}/lock",
    response_model=LockVideoResponse,
    summary="Заблокувати відео",
    description="Блокує відео для анотації поточним користувачем. Запобігає одночасній роботі кількох користувачів",
    responses={
        404: {"model": ErrorResponse, "description": "Відео не знайдено"},
        409: {"model": ErrorResponse, "description": "Відео вже заблоковано іншим користувачем"},
        400: {"model": ErrorResponse, "description": "Відео не готове для анотації"}
    }
)
async def lock_video(
        video_id: str,
        current_user: Annotated[dict, Depends(get_current_user)],
        video_service: Annotated[VideoService, Depends(VideoService)]
) -> LockVideoResponse:
    """Блокування відео для анотації"""
    return video_service.lock_video_for_annotation(
        video_id=video_id,
        user_id=current_user["user_id"],
        user_email=current_user["email"]
    )


@router.post(
    "/{video_id}/unlock",
    summary="Розблокувати відео",
    description="Знімає блокування з відео. Користувач може розблокувати тільки власні блокування",
    responses={
        400: {"model": ErrorResponse, "description": "Не можна розблокувати відео іншого користувача"}
    }
)
async def unlock_video(
        video_id: str,
        current_user: Annotated[dict, Depends(get_current_user)],
        video_service: Annotated[VideoService, Depends(VideoService)]
):
    """Розблокування відео"""
    return video_service.unlock_video_for_annotation(
        video_id=video_id,
        user_id=current_user["user_id"]
    )


@router.get(
    "/{video_id}/stream",
    summary="Безпечний стрімінг відео",
    description="Повертає відео файл для перегляду в анотаторі використовуючи video_id. Безпечніший варіант без Azure деталей в URL",
    responses={
        404: {"model": ErrorResponse, "description": "Відео не знайдено"},
        400: {"model": ErrorResponse, "description": "Відео не готове або файл не знайдено"},
        403: {"model": ErrorResponse, "description": "Недостатньо прав для перегляду"}
    }
)
async def stream_video_by_id(
        video_id: str,
        video_service: Annotated[VideoService, Depends(VideoService)],
        token: str = Query(..., description="Authorization token")
) -> FileResponse:
    """Безпечний стрімінг локального відео за video_id"""
    # Перевіряємо токен вручну
    auth_service = AuthService()
    current_user = auth_service.get_current_user_from_token(token)
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Невалідний або прострочений токен")
    
    # Перевіряємо права доступу (annotator, admin, super_admin)
    if current_user.role not in ["annotator", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Недостатньо прав для перегляду відео")
    
    file_info = video_service.get_video_file_for_streaming_by_id(video_id, current_user.user_id)

    return FileResponse(
        path=file_info["file_path"],
        media_type="video/mp4",
        filename=file_info["filename"],
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Content-Type": "video/mp4"
        }
    )



