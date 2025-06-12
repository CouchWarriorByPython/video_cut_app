from fastapi import Request
from fastapi.responses import JSONResponse
from backend.services.auth_service import AuthService
from backend.utils.logger import get_logger

logger = get_logger(__name__, "middleware.log")


async def auth_middleware(request: Request, call_next):
    """Мідлвейр для перевірки авторизації"""

    # Публічні шляхи що не потребують авторизації
    public_paths = [
        "/auth/login",
        "/auth/refresh",
        "/login",
        "/docs",
        "/openapi.json",
        "/health",
        "/favicon.ico",
        "/favicon.png"
    ]

    # Перевіряємо чи це публічний шлях
    request_path = request.url.path
    if (request_path in public_paths or
        request_path.startswith("/static") or
        request_path.startswith("/css") or
        request_path.startswith("/js")):
        return await call_next(request)

    # Для HTML сторінок - дозволяємо показати сторінку, JavaScript сам перевірить авторизацію
    is_html_request = request.headers.get("accept", "").startswith("text/html")
    if is_html_request:
        return await call_next(request)

    # Для API запитів - перевіряємо авторизацію
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning(f"Відсутній Authorization header для {request.method} {request.url}")
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Authorization header відсутній"}
        )

    try:
        # Парсимо заголовок
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

        # Зберігаємо інформацію про користувача в request
        request.state.user = {
            "user_id": payload["user_id"],
            "email": payload["sub"],
            "role": payload["role"]
        }

        logger.debug(f"Авторизація успішна: {payload['sub']} ({payload['role']})")

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