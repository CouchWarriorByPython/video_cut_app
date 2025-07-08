from fastapi import Request
from fastapi.responses import JSONResponse
from backend.services.auth_service import AuthService
from backend.utils.logger import get_logger

logger = get_logger(__name__, "middleware.log")

# Конфігурація доступу до ендпоінтів
ENDPOINT_PERMISSIONS = {
    # Публічні ендпоінти
    "/auth/login": None,
    "/auth/refresh": None,
    "/login": None,
    "/docs": None,
    "/openapi.json": None,
    "/health": None,
    "/favicon.ico": None,
    "/favicon.png": None,
    "/get_video": None,


    # HTML сторінки (JavaScript сам перевіряє)
    "/": "html",
    "/annotator": "html",
    "/faq": "html",

    # API ендпоінти з ролями
    "/upload": ["admin", "super_admin"],
    "/task_status": ["admin", "super_admin"],
    "/video_status": ["annotator", "admin", "super_admin"],
    "/get_videos": ["annotator", "admin", "super_admin"],
    "/get_annotation": ["annotator", "admin", "super_admin"],
    "/save_fragments": ["annotator", "admin", "super_admin"],

    # Admin panel
    "/admin": "html",
    "/admin/": "html",
    "/admin/stats": ["admin", "super_admin"],
    "/admin/users": ["admin", "super_admin"],
    "/admin/cvat-settings": ["admin", "super_admin"],
}


async def auth_middleware(request: Request, call_next):
    """Централізований мідлвейр авторизації"""

    request_path = request.url.path
    method = request.method

    # Статичні файли завжди дозволені
    if (request_path.startswith("/static") or
            request_path.startswith("/css") or
            request_path.startswith("/js")):
        return await call_next(request)

    # Перевіряємо права доступу
    required_permission = get_endpoint_permission(request_path, method)

    # Публічні ендпоінти
    if required_permission is None:
        return await call_next(request)



    # HTML сторінки - дозволяємо показ, JS сам перевірить
    if required_permission == "html":
        is_html_request = request.headers.get("accept", "").startswith("text/html")
        if is_html_request:
            return await call_next(request)
        # Якщо це не HTML запит на HTML ендпоінт - треба авторизація
        required_permission = ["annotator", "admin", "super_admin"]

    # Перевіряємо токен
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning(f"Missing Authorization header for {method} {request.url}")
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Authorization header відсутній"}
        )

    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Невірна схема авторизації"}
            )

        # Використовуємо AuthService для перевірки токена
        auth_service = AuthService()
        current_user = auth_service.get_current_user_from_token(token)

        if not current_user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Невалідний або прострочений токен"}
            )

        # Перевіряємо ролі
        if isinstance(required_permission, list):
            if current_user.role not in required_permission:
                logger.warning(
                    f"🚫 Access denied for {current_user.email} "
                    f"(role: {current_user.role}, required: {required_permission})"
                )
                return JSONResponse(
                    status_code=403,
                    content={"success": False, "message": "Недостатньо прав доступу"}
                )

        # Зберігаємо дані користувача як dict для сумісності з API
        request.state.user = current_user.model_dump()
        logger.debug(f"✅ Authorization successful: {current_user.email} ({current_user.role})")

    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Невірний формат токена"}
        )
    except Exception as e:
        logger.error(f"Error in auth_middleware: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Внутрішня помилка сервера"}
        )

    return await call_next(request)


def get_endpoint_permission(path: str, method: str) -> str | list[str] | None:
    """Отримує права доступу для ендпоінта"""

    # Точний збіг
    if path in ENDPOINT_PERMISSIONS:
        return ENDPOINT_PERMISSIONS[path]

    # Перевіряємо паттерни
    if path.startswith("/task_status/"):
        return ENDPOINT_PERMISSIONS["/task_status"]

    # Всі операції з користувачами тільки для адмінів
    if path.startswith("/users/"):
        return ["admin", "super_admin"]

    # Відео стрімінг - перевіряємо токен вручну в endpoint
    if path.startswith("/video/") and path.endswith("/stream"):
        return None

    # За замовчуванням вимагаємо авторизацію
    return ["annotator", "admin", "super_admin"]