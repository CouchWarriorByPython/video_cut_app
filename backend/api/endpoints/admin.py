from typing import List, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.models.api import (
    UserCreate, UserResponse, UserCreateResponse, UserDeleteResponse,
    UserUpdateRequest, AdminStatsResponse, ErrorResponse
)
from backend.models.shared import CVATSettings
from backend.services.admin_service import AdminService
from backend.api.dependencies import require_admin_role
from backend.api.exceptions import ValidationException, ConflictException
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Отримати статистику системи",
    description="Повертає загальну статистику по користувачах та відео",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка отримання статистики"}
    }
)
async def get_admin_stats(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
) -> AdminStatsResponse:
    """Отримати адміністративну статистику"""
    logger.info(f"Admin {current_user['email']} requested statistics")
    return admin_service.get_system_statistics_response()


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="Отримати список користувачів",
    description="Повертає список всіх користувачів системи для адміністрування",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка отримання користувачів"}
    }
)
async def get_all_users_admin(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
) -> List[UserResponse]:
    """Отримати всіх користувачів для адмін панелі"""
    logger.info(f"Admin {current_user['email']} requested users list")
    return admin_service.get_all_users_response()


@router.post(
    "/users",
    response_model=UserCreateResponse,
    summary="Створити нового користувача",
    description="Створює нового користувача з вказаною роллю. Тільки super_admin може створювати admin користувачів",
    responses={
        400: {"model": ErrorResponse, "description": "Недостатньо прав для створення користувача з такою роллю"},
        409: {"model": ErrorResponse, "description": "Користувач з таким email вже існує"},
        422: {"model": ErrorResponse, "description": "Помилка валідації даних"}
    }
)
async def create_user_admin(
        user_data: UserCreate,
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
) -> UserCreateResponse:
    """Створити нового користувача"""
    try:
        result = admin_service.create_user_with_validation(
            email=user_data.email,
            password=user_data.password,
            role=user_data.role,
            current_user_role=current_user["role"]
        )

        logger.info(f"User {user_data.email} created by admin {current_user['email']}")
        return result

    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ConflictException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка створення користувача: {str(e)}")


@router.put(
    "/users/{user_id}",
    summary="Оновити користувача",
    description="Оновлює дані існуючого користувача. Не можна редагувати самого себе",
    responses={
        400: {"model": ErrorResponse, "description": "Не можна редагувати самого себе або недостатньо прав"},
        404: {"model": ErrorResponse, "description": "Користувач не знайдений"},
        409: {"model": ErrorResponse, "description": "Email вже використовується"},
        422: {"model": ErrorResponse, "description": "Помилка валідації даних"}
    }
)
async def update_user_admin(
        user_id: str,
        user_data: UserUpdateRequest,
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Оновити існуючого користувача"""
    return admin_service.update_user_with_validation(
        user_id=user_id,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role,
        current_user_id=current_user["user_id"],
        current_user_role=current_user["role"]
    )


@router.delete(
    "/users/{user_id}",
    response_model=UserDeleteResponse,
    summary="Видалити користувача",
    description="Видаляє користувача з системи. Не можна видалити самого себе",
    responses={
        400: {"model": ErrorResponse, "description": "Не можна видалити самого себе або недостатньо прав"},
        404: {"model": ErrorResponse, "description": "Користувач не знайдений"}
    }
)
async def delete_user_admin(
        user_id: str,
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
) -> UserDeleteResponse:
    """Видалити користувача"""
    return admin_service.delete_user_with_validation(
        user_id=user_id,
        current_user_id=current_user["user_id"],
        current_user_role=current_user["role"]
    )


@router.get(
    "/cvat-settings",
    response_model=List[CVATSettings],
    summary="Отримати налаштування CVAT",
    description="Повертає налаштування для всіх CVAT проєктів",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка отримання налаштувань"}
    }
)
async def get_cvat_settings(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
) -> List[CVATSettings]:
    """Отримати налаштування CVAT проєктів"""
    logger.info(f"Admin {current_user['email']} requested CVAT settings")
    return admin_service.get_cvat_settings_response()


@router.put(
    "/cvat-settings/{project_name}",
    summary="Оновити налаштування CVAT проєкту",
    description="Оновлює параметри CVAT для вказаного ML проєкту",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка оновлення налаштувань"},
        422: {"model": ErrorResponse, "description": "Project name in URL and body must match"}
    }
)
async def update_cvat_settings(
        project_name: str,
        settings_data: CVATSettings,
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Оновити налаштування CVAT проєкту"""
    if settings_data.project_name.value != project_name:
        raise ValidationException("Project name in URL and body must match")

    result = admin_service.update_cvat_settings_with_model(settings_data)

    logger.info(f"CVAT settings for {project_name} updated by admin {current_user['email']}")
    return result


@router.post(
    "/reset-cvat-settings",
    summary="Скинути CVAT налаштування до дефолтних",
    description="Скидає всі CVAT налаштування проєктів до дефолтних значень",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка скидання налаштувань"}
    }
)
async def reset_cvat_settings(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Скинути всі CVAT налаштування до дефолтних значень"""
    result = admin_service.reset_cvat_settings_to_defaults()
    
    logger.info(f"CVAT settings reset to defaults by admin {current_user['email']}")
    return result


@router.post(
    "/fix-orphaned-videos",
    summary="Виправити відео зі статусом IN_PROGRESS, які не заблоковані",
    description="Виправляє відео, які мають статус 'В процесі анотації', але не заблоковані (виникає після перезапуску сервісу)",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка виправлення відео"}
    }
)
async def fix_orphaned_videos(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Виправляти відео зі статусом IN_PROGRESS, які не заблоковані"""
    result = admin_service.fix_orphaned_in_progress_videos()
    
    logger.info(f"Fixed orphaned IN_PROGRESS videos by admin {current_user['email']}")
    return result


@router.delete(
    "/videos/{video_id}",
    summary="Видалити відео",
    description="Видаляє відео з системи: локальний файл та запис з бази даних",
    responses={
        404: {"model": ErrorResponse, "description": "Відео не знайдено"},
        400: {"model": ErrorResponse, "description": "Помилка видалення відео"}
    }
)
async def delete_video(
        video_id: str,
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Видалити відео для адмінів"""
    result = admin_service.delete_video(video_id)
    
    logger.info(f"Video {video_id} deleted by admin {current_user['email']}")
    return result


@router.get(
    "/videos",
    summary="Отримати список всіх відео для адмінів",
    description="Повертає пагінований список всіх відео з додатковою інформацією для адмінів",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка отримання списку відео"}
    }
)
async def get_admin_videos(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)],
        page: int = Query(1, ge=1, description="Номер сторінки"),
        per_page: int = Query(20, ge=1, le=100, description="Кількість відео на сторінку")
):
    """Отримати список всіх відео для адмін панелі"""
    logger.info(f"Admin {current_user['email']} requested videos list (page {page})")
    return admin_service.get_admin_videos_list(page=page, per_page=per_page)


@router.get(
    "/system-health",
    summary="Діагностика стану системи",
    description="Повертає детальну інформацію про стан Redis, MongoDB та інших компонентів",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка отримання інформації про систему"}
    }
)
async def get_system_health(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Діагностика стану системи"""
    logger.info(f"Admin {current_user['email']} requested system health check")
    return admin_service.get_system_health_info()


@router.post(
    "/cleanup-locks",
    summary="Очистити застарілі блокування",
    description="Видаляє всі прострочені блокування відео з Redis",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка очищення блокувань"}
    }
)
async def cleanup_video_locks(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Очистити застарілі блокування відео"""
    logger.info(f"Admin {current_user['email']} requested video locks cleanup")
    return admin_service.cleanup_video_locks()


@router.post(
    "/force-cleanup-locks",
    summary="Примусове видалення всіх блокувань",
    description="УВАГА: Видаляє ВСІ блокування відео, включно з активними. Використовувати тільки в екстрених ситуаціях",
    responses={
        400: {"model": ErrorResponse, "description": "Помилка примусового очищення"}
    }
)
async def force_cleanup_all_locks(
        current_user: Annotated[dict, Depends(require_admin_role)],
        admin_service: Annotated[AdminService, Depends(AdminService)]
):
    """Примусове видалення всіх блокувань відео"""
    logger.warning(f"Admin {current_user['email']} requested FORCE cleanup of all video locks")
    return admin_service.force_cleanup_all_locks()
