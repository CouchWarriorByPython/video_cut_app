from typing import Dict, Any, List
from fastapi import Request, HTTPException, Depends

from backend.models.api import (
    VideoAnnotationResponse, VideoMetadataResponse,
    CVATProjectParamsResponse, ClipInfoResponse
)
from backend.utils.logger import get_logger

logger = get_logger(__name__, "auth.log")


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


# Auth Dependencies

def get_current_user(request: Request) -> Dict[str, Any]:
    """Отримує поточного користувача з request state"""
    if not hasattr(request.state, "user"):
        logger.warning(f"🚫 Спроба доступу без авторизації: {request.url}")
        raise HTTPException(
            status_code=401,
            detail="Користувач не авторизований"
        )

    logger.info(f"✅ Авторизований запит від {request.state.user['email']}")
    return request.state.user


def require_roles(allowed_roles: List[str]):
    """Декоратор для перевірки ролей користувача"""

    def check_role(current_user: Dict[str, Any] = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            logger.warning(
                f"🚫 Доступ заборонено для {current_user['email']} "
                f"(роль: {current_user['role']}, потрібна: {allowed_roles})"
            )
            raise HTTPException(
                status_code=403,
                detail="Недостатньо прав доступу"
            )
        return current_user

    return check_role


def require_super_admin():
    """Потребує роль super_admin"""
    return require_roles(["super_admin"])


def require_admin_or_super():
    """Потребує роль admin або super_admin"""
    return require_roles(["admin", "super_admin"])


def require_any_role():
    """Потребує будь-яку роль (просто авторизований користувач)"""
    return require_roles(["annotator", "admin", "super_admin"])