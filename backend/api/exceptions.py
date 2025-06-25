from typing import cast, Optional, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")


# =================== КАСТОМНІ EXCEPTION КЛАСИ ===================

class APIException(Exception):
    """Базовий клас для всіх API помилок"""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(APIException):
    """Помилки валідації даних"""

    def __init__(self, message: str = "Помилка валідації даних", details: Optional[Dict] = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR", details)


class AuthenticationException(APIException):
    """Помилки автентифікації"""

    def __init__(self, message: str = "Потрібна автентифікація"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, "AUTHENTICATION_ERROR")


class AuthorizationException(APIException):
    """Помилки авторизації (недостатньо прав)"""

    def __init__(self, message: str = "Недостатньо прав доступу"):
        super().__init__(message, status.HTTP_403_FORBIDDEN, "AUTHORIZATION_ERROR")


class NotFoundException(APIException):
    """Ресурс не знайдено"""

    def __init__(self, resource: str = "Ресурс", resource_id: Optional[str] = None):
        message = f"{resource} не знайдено"
        if resource_id:
            message += f" (ID: {resource_id})"
        super().__init__(message, status.HTTP_404_NOT_FOUND, "NOT_FOUND", {"resource": resource, "id": resource_id})


class ConflictException(APIException):
    """Конфлікт ресурсів"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status.HTTP_409_CONFLICT, "CONFLICT_ERROR", details)


class BusinessLogicException(APIException):
    """Помилки бізнес логіки"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, "BUSINESS_LOGIC_ERROR", details)


# =================== СПЕЦІАЛІЗОВАНІ EXCEPTION ДЛЯ ПРОЄКТУ ===================

class VideoNotFoundException(NotFoundException):
    """Відео не знайдено"""

    def __init__(self, video_id: Optional[str] = None):
        super().__init__("Відео", video_id)


class VideoAlreadyLockedException(ConflictException):
    """Відео вже заблоковано"""

    def __init__(self, locked_by: str, expires_at: Optional[str] = None):
        message = f"Відео вже заблоковано користувачем {locked_by}"
        details = {"locked_by": locked_by}
        if expires_at:
            message += f" до {expires_at}"
            details["expires_at"] = expires_at
        super().__init__(message, details)


class VideoNotReadyException(BusinessLogicException):
    """Відео не готове для операції"""

    def __init__(self, current_status: str, required_status: Optional[str] = None):
        message = f"Відео має статус '{current_status}'"
        if required_status:
            message += f", а потрібен '{required_status}'"
        super().__init__(message, {"current_status": current_status, "required_status": required_status})


class InvalidTokenException(AuthenticationException):
    """Невалідний токен"""

    def __init__(self, reason: str = "Токен невалідний або прострочений"):
        super().__init__(f"Невалідний токен: {reason}")


class InsufficientPermissionsException(AuthorizationException):
    """Недостатньо прав для операції"""

    def __init__(self, required_role: str, current_role: str):
        message = f"Потрібна роль '{required_role}', а у вас '{current_role}'"
        super().__init__(message)
        self.details = {"required_role": required_role, "current_role": current_role}


class FileProcessingException(APIException):
    """Помилки обробки файлів"""

    def __init__(self, message: str, file_path: Optional[str] = None):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, "FILE_PROCESSING_ERROR")
        if file_path:
            self.details["file_path"] = file_path


class ExternalServiceException(APIException):
    """Помилки зовнішніх сервісів (Azure, CVAT)"""

    def __init__(self, service: str, message: str, details: Optional[Dict] = None):
        super().__init__(f"Помилка сервісу {service}: {message}",
                         status.HTTP_502_BAD_GATEWAY, "EXTERNAL_SERVICE_ERROR", details)


# =================== ОБРОБНИКИ ПОМИЛОК ===================

def api_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник кастомних API помилок"""
    api_exc = cast(APIException, exc)
    logger.warning(f"API помилка {api_exc.error_code} для {request.method} {request.url.path}: {api_exc.message}")

    content = {
        "success": False,
        "message": api_exc.message,
        "error_code": api_exc.error_code,
        "timestamp": getattr(request.state, 'request_time', None)
    }

    if api_exc.details:
        content["details"] = api_exc.details

    return JSONResponse(
        status_code=api_exc.status_code,
        content=content
    )


def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник помилок валідації Pydantic"""
    validation_error = cast(RequestValidationError, exc)

    errors = []
    for error in validation_error.errors():
        field_name = '.'.join(str(x) for x in error['loc'][1:]) if len(error['loc']) > 1 else 'unknown'
        errors.append({
            "field": field_name,
            "message": error['msg'],
            "input": error.get('input'),
            "type": error.get('type')
        })

    logger.warning(f"Помилка валідації для {request.method} {request.url.path}: {len(errors)} помилок")

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Помилка валідації даних",
            "error_code": "VALIDATION_ERROR",
            "errors": errors,
            "timestamp": getattr(request.state, 'request_time', None)
        }
    )


def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник стандартних HTTP помилок"""
    http_error = cast(StarletteHTTPException, exc)
    logger.warning(
        f"HTTP помилка {http_error.status_code} для {request.method} {request.url.path}: {http_error.detail}")

    # Переклад стандартних повідомлень
    message_translations = {
        404: "Ендпоінт не знайдено",
        405: "Метод не дозволено",
        406: "Неприйнятний формат",
        415: "Непідтримуваний тип контенту",
        413: "Запит занадто великий",
        429: "Забагато запитів"
    }

    message = message_translations.get(http_error.status_code, str(http_error.detail))

    return JSONResponse(
        status_code=http_error.status_code,
        content={
            "success": False,
            "message": message,
            "error_code": f"HTTP_{http_error.status_code}",
            "timestamp": getattr(request.state, 'request_time', None)
        }
    )


def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник непередбачуваних помилок"""
    logger.error(f"Необроблена помилка для {request.method} {request.url.path}: {str(exc)}", exc_info=True)

    # У продакшені не показуємо деталі помилки
    from backend.config.settings import get_settings
    settings = get_settings()

    content = {
        "success": False,
        "message": "Внутрішня помилка сервера",
        "error_code": "INTERNAL_SERVER_ERROR",
        "timestamp": getattr(request.state, 'request_time', None)
    }

    # В розробці показуємо деталі
    if settings.is_local_environment:
        content["debug_info"] = str(exc)

    return JSONResponse(
        status_code=500,
        content=content
    )


# =================== HELPER ФУНКЦІЇ ===================

def raise_not_found(resource: str, resource_id: Optional[str] = None) -> None:
    """Швидке підняття NotFound помилки"""
    raise NotFoundException(resource, resource_id)


def raise_business_error(message: str, details: Optional[Dict] = None) -> None:
    """Швидке підняття бізнес помилки"""
    raise BusinessLogicException(message, details)


def raise_auth_error(message: str = "Потрібна автентифікація") -> None:
    """Швидке підняття помилки автентифікації"""
    raise AuthenticationException(message)


def raise_permission_error(required_role: str, current_role: str) -> None:
    """Швидке підняття помилки прав доступу"""
    raise InsufficientPermissionsException(required_role, current_role)