from typing import Dict, Any, Annotated
from fastapi import Request, Query, Depends
from backend.models.shared import AzureFilePath
from backend.api.exceptions import AuthorizationException


def get_current_user(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency для отримання поточного користувача.
    Middleware вже перевірив токен, тому просто беремо дані з request.state
    """
    return request.state.user


def get_azure_path_from_query(
    account_name: str = Query(..., description="Назва Azure storage account"),
    container_name: str = Query(..., description="Назва контейнера"),
    blob_path: str = Query(..., description="Шлях до blob")
) -> AzureFilePath:
    """
    Dependency для парсингу Azure path з query параметрів.
    Використовується в ендпоінтах, які працюють з Azure файлами
    """
    return AzureFilePath(
        account_name=account_name,
        container_name=container_name,
        blob_path=blob_path
    )


def get_pagination_params(
    page: int = Query(1, ge=1, description="Номер сторінки"),
    per_page: int = Query(20, ge=1, le=100, description="Кількість елементів на сторінку")
) -> Dict[str, int]:
    """
    Dependency для пагінації.
    Повертає стандартні параметри пагінації
    """
    return {"page": page, "per_page": per_page}


def require_admin_role(current_user: Annotated[dict, Depends(get_current_user)]) -> Dict[str, Any]:
    """
    Dependency що перевіряє чи користувач має admin або super_admin роль.
    Використовується для адмін ендпоінтів
    """
    if current_user["role"] not in ["admin", "super_admin"]:
        raise AuthorizationException("Потрібна роль адміністратора")
    return current_user


def require_super_admin_role(current_user: Annotated[dict, Depends(get_current_user)]) -> Dict[str, Any]:
    """
    Dependency що перевіряє чи користувач має super_admin роль.
    Використовується для критичних операцій
    """
    if current_user["role"] != "super_admin":
        raise AuthorizationException("Потрібна роль супер адміністратора")
    return current_user