from typing import List
from fastapi import APIRouter, HTTPException, Depends

from backend.models.user import UserCreate, UserResponse, UserCreateResponse, UserDeleteResponse
from backend.services.auth_service import AuthService
from backend.database.repositories.user import UserRepository
from backend.api.dependencies import require_admin_or_super, get_current_user
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserCreateResponse, dependencies=[Depends(require_admin_or_super())])
async def create_user(user_data: UserCreate, current_user: dict = Depends(get_current_user)) -> UserCreateResponse:
    """Створення користувача (admin може створювати тільки annotator, super_admin - всіх)"""

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


@router.get("/", response_model=List[UserResponse], dependencies=[Depends(require_admin_or_super())])
async def get_users() -> List[UserResponse]:
    """Отримання списку користувачів (тільки admin та super_admin)"""
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


@router.delete("/{user_id}", response_model=UserDeleteResponse)
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)) -> UserDeleteResponse:
    """Видалення користувача (admin може видаляти annotator, super_admin - всіх)"""
    user_repo = UserRepository()

    # Отримуємо інформацію про користувача що видаляється
    user_to_delete = user_repo.get_user_by_id(user_id)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    # Перевіряємо права на видалення
    if current_user["role"] == "annotator":
        raise HTTPException(
            status_code=403,
            detail="Анотатори не можуть видаляти користувачів"
        )

    if user_to_delete["role"] == "admin" and current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Тільки super_admin може видаляти адміністраторів"
        )

    if user_to_delete["role"] == "super_admin" and current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Тільки super_admin може видаляти інших super_admin"
        )

    # Заборонити видалення самого себе
    if user_to_delete["_id"] == current_user["user_id"]:
        raise HTTPException(
            status_code=400,
            detail="Не можна видалити самого себе"
        )

    success = user_repo.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Помилка видалення користувача")

    logger.info(f"Користувач {user_to_delete['email']} видалений адміністратором {current_user['email']}")
    return UserDeleteResponse(success=True, message="Користувача успішно видалено")