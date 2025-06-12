import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.exceptions import (
    validation_exception_handler, http_exception_handler, general_exception_handler
)
from backend.api.endpoints import video, annotation, static, auth, users
from backend.middlewares.auth_middleware import auth_middleware
from backend.middlewares.log_middleware import log_middleware
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "main.log")

app = FastAPI(
    title="Video Annotation API",
    description="API для завантаження, анотування та обробки відео з авторизацією",
    version="1.0.0"
)

# Додаємо мідлвейри (порядок важливий!)
app.middleware("http")(log_middleware)
app.middleware("http")(auth_middleware)

# Реєстрація обробників помилок
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Монтування статичних файлів
if os.path.exists("front/static"):
    app.mount("/static", StaticFiles(directory="front/static"), name="static")
    logger.info("Статичні файли змонтовано з директорії 'front/static'")
elif os.path.exists("front"):
    app.mount("/static", StaticFiles(directory="front"), name="static")
    logger.info("Статичні файли змонтовано з директорії 'front'")
else:
    logger.warning("Директорія 'front' не знайдена")

# Підключення роутерів
app.include_router(auth.router)  # Додаємо роутер авторизації
app.include_router(users.router)  # Додаємо роутер користувачів
app.include_router(video.router)
app.include_router(annotation.router)
app.include_router(static.router)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "video-annotation-api"}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"MongoDB URI: {Settings.mongo_uri}")
    logger.info(f"Запуск сервера на {Settings.fast_api_host}:{Settings.fast_api_port}")

    uvicorn.run(
        "backend.main:app",
        host=Settings.fast_api_host,
        port=Settings.fast_api_port,
        reload=Settings.reload,
        log_level="info"
    )