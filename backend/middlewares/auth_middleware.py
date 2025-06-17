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

    # HTML сторінки
    "/": ["admin", "super_admin"],  # Тільки адміни можуть завантажувати відео
    "/annotator": ["annotator", "admin", "super_admin"],
    "/faq": ["annotator", "admin", "super_admin"],

    # API ендпоінти з ролями
    "/upload": ["admin", "super_admin"],  # Тільки адміни можуть завантажувати
    "/task_status": ["admin", "super_admin"],  # Тільки адміни можуть перевіряти статус
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
        logger.warning(f"Відсутній Authorization header для {method} {request.url}")
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

        # Перевіряємо токен
        auth_service = AuthService()
        payload = auth_service.verify_token(token)

        if not payload:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Невалідний або прострочений токен"}
            )

        user_data = {
            "user_id": payload["user_id"],
            "email": payload["sub"],
            "role": payload["role"]
        }

        # Перевіряємо ролі
        if isinstance(required_permission, list):
            if user_data["role"] not in required_permission:
                logger.warning(
                    f"🚫 Доступ заборонено для {user_data['email']} "
                    f"(роль: {user_data['role']}, потрібна: {required_permission})"
                )
                return JSONResponse(
                    status_code=403,
                    content={"success": False, "message": "Недостатньо прав доступу"}
                )

        # Зберігаємо дані користувача
        request.state.user = user_data
        logger.debug(f"✅ Авторизація успішна: {payload['sub']} ({payload['role']})")

    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Невірний формат токена"}
        )
    except Exception as e:
        logger.error(f"Помилка в auth_middleware: {str(e)}")
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
        return ENDPOINT_PERMISSIONS["/users"]

    # За замовчуванням вимагаємо авторизацію
    return ["annotator", "admin", "super_admin"]