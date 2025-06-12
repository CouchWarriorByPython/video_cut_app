import time
from fastapi import Request
from backend.utils.logger import get_logger

logger = get_logger(__name__, "middleware.log")


async def log_middleware(request: Request, call_next):
    """Мідлвейр для логування запитів"""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"

    # Логуємо вхідний запит
    logger.info(f"Запит від {client_ip}: {request.method} {request.url.path}")

    # Обробляємо запит
    response = await call_next(request)

    # Логуємо відповідь
    process_time = time.time() - start_time
    logger.info(
        f"Запит від {client_ip} завершено за {process_time:.3f}с "
        f"зі статусом {response.status_code}"
    )

    return response