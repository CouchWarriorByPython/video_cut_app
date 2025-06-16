from typing import List
from fastapi import APIRouter, HTTPException, Request

from backend.models.user import UserCreate, UserResponse, UserCreateResponse, UserDeleteResponse
from backend.models.cvat_settings import (
    CVATSettingsRequest, CVATSettingsResponse, AdminStatsResponse
)
from backend.services.auth_service import AuthService
from backend.database.repositories.user import UserRepository
from backend.database.repositories.cvat_settings import CVATSettingsRepository
from backend.database.repositories.source_video import SyncSourceVideoRepository
from backend.api.dependencies import get_current_user
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(request: Request) -> AdminStatsResponse:
    """Отримання статистики для адмін панелі"""
    current_user = get_current_user(request)
    logger.info(f"Адмін {current_user['email']} запросив статистику")

    try:
        user_repo = UserRepository()
        video_repo = SyncSourceVideoRepository()

        # Статистика користувачів
        all_users = user_repo.get_all_users()
        total_users = len(all_users)
        active_users = len([u for u in all_users if u.get("is_active", True)])

        # Статистика відео
        all_videos = video_repo.get_all_annotations()
        total_videos = len(all_videos)
        processing_videos = len(
            [v for v in all_videos if v.get("status") not in ["ready", "not_annotated", "annotated"]])
        annotated_videos = len([v for v in all_videos if v.get("status") == "annotated"])

        return AdminStatsResponse(
            total_users=total_users,
            active_users=active_users,
            total_videos=total_videos,
            processing_videos=processing_videos,
            annotated_videos=annotated_videos
        )

    except Exception as e:
        logger.error(f"Помилка отримання статистики: {str(e)}")
        raise HTTPException(status_code=500, detail="Помилка отримання статистики")


@router.get("/users", response_model=List[UserResponse])
async def get_all_users_admin(request: Request) -> List[UserResponse]:
    """Отримання всіх користувачів для адмін панелі"""
    current_user = get_current_user(request)
    logger.info(f"Адмін {current_user['email']} запросив список користувачів")

    user_repo = UserRepository()
    users = user_repo.get_all_users()

    return [
        UserResponse(
            id=user["_id"],
            email=user["email"],
            role=user["role"],
            created_at=user["created_at"],
            is_active=user["is_active"]
        )
        for user in users
    ]


@router.post("/users", response_model=UserCreateResponse)
async def create_user_admin(user_data: UserCreate, request: Request) -> UserCreateResponse:
    """Створення користувача через адмін панель"""
    current_user = get_current_user(request)

    # Перевіряємо права на створення адміна
    if user_data.role == "admin" and current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Тільки super_admin може створювати адміністраторів"
        )

    auth_service = AuthService()
    result = auth_service.create_user(user_data.email, user_data.password, user_data.role)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    logger.info(f"Користувач {user_data.email} створений адміністратором {current_user['email']}")
    return UserCreateResponse(
        success=True,
        message=result["message"],
        user_id=result["user_id"]
    )


@router.put("/users/{user_id}/role")
async def update_user_role(user_id: str, new_role: str, request: Request):
    """Оновлення ролі користувача"""
    current_user = get_current_user(request)

    if new_role not in ["annotator", "admin"]:
        raise HTTPException(status_code=400, detail="Невірна роль")

    if new_role == "admin" and current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Тільки super_admin може призначати роль admin"
        )

    user_repo = UserRepository()
    user_to_update = user_repo.get_user_by_id(user_id)

    if not user_to_update:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    if user_to_update["_id"] == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Не можна змінити власну роль")

    success = user_repo.update_user(user_id, {"role": new_role})
    if not success:
        raise HTTPException(status_code=400, detail="Помилка оновлення ролі")

    logger.info(
        f"Роль користувача {user_to_update['email']} змінена на {new_role} адміністратором {current_user['email']}")
    return {"success": True, "message": "Роль успішно оновлена"}


@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
async def delete_user_admin(user_id: str, request: Request) -> UserDeleteResponse:
    """Видалення користувача через адмін панель"""
    current_user = get_current_user(request)
    user_repo = UserRepository()

    user_to_delete = user_repo.get_user_by_id(user_id)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    if current_user["role"] == "annotator":
        raise HTTPException(status_code=403, detail="Анотатори не можуть видаляти користувачів")

    if user_to_delete["role"] == "admin" and current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Тільки super_admin може видаляти адміністраторів")

    if user_to_delete["role"] == "super_admin" and current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Тільки super_admin може видаляти інших super_admin")

    if user_to_delete["_id"] == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Не можна видалити самого себе")

    success = user_repo.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Помилка видалення користувача")

    logger.info(f"Користувач {user_to_delete['email']} видалений адміністратором {current_user['email']}")
    return UserDeleteResponse(success=True, message="Користувача успішно видалено")


@router.get("/cvat-settings", response_model=List[CVATSettingsResponse])
async def get_cvat_settings(request: Request) -> List[CVATSettingsResponse]:
    """Отримання всіх налаштувань CVAT проєктів"""
    current_user = get_current_user(request)
    logger.info(f"Адмін {current_user['email']} запросив налаштування CVAT")

    try:
        settings_repo = CVATSettingsRepository()
        settings_repo.create_indexes()

        # Ініціалізуємо дефолтні налаштування якщо їх немає
        settings_repo.initialize_default_settings()

        all_settings = settings_repo.get_all_settings()

        return [
            CVATSettingsResponse(
                id=setting["_id"],
                project_name=setting["project_name"],
                project_id=setting["project_id"],
                overlap=setting["overlap"],
                segment_size=setting["segment_size"],
                image_quality=setting["image_quality"],
                created_at=setting["created_at"],
                updated_at=setting["updated_at"]
            )
            for setting in all_settings
        ]

    except Exception as e:
        logger.error(f"Помилка отримання налаштувань CVAT: {str(e)}")
        raise HTTPException(status_code=500, detail="Помилка отримання налаштувань")


@router.put("/cvat-settings/{project_name}")
async def update_cvat_settings(
        project_name: str,
        settings_data: CVATSettingsRequest,
        request: Request
):
    """Оновлення налаштувань CVAT проєкту"""
    current_user = get_current_user(request)

    if project_name not in ["motion-det", "tracking", "mil-hardware", "re-id"]:
        raise HTTPException(status_code=400, detail="Невірна назва проєкту")

    try:
        from backend.models.cvat_settings import CVATProjectSettings

        settings = CVATProjectSettings(
            project_name=project_name,
            project_id=settings_data.project_id,
            overlap=settings_data.overlap,
            segment_size=settings_data.segment_size,
            image_quality=settings_data.image_quality
        )

        settings_repo = CVATSettingsRepository()
        settings_id = settings_repo.save_settings(settings)

        logger.info(f"Налаштування проєкту {project_name} оновлені адміністратором {current_user['email']}")

        return {
            "success": True,
            "message": "Налаштування успішно оновлені",
            "id": settings_id
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Помилка оновлення налаштувань CVAT: {str(e)}")
        raise HTTPException(status_code=500, detail="Помилка оновлення налаштувань")