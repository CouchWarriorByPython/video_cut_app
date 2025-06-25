import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.exceptions import (
    APIException, api_exception_handler,
    validation_exception_handler, http_exception_handler, general_exception_handler
)

from backend.api.endpoints import video, annotation, static, auth, admin
from backend.middlewares.auth_middleware import auth_middleware
from backend.middlewares.log_middleware import log_middleware
from backend.database.connection import DatabaseConnection
from backend.config.settings import get_settings
from backend.utils.logger import get_logger
from backend.utils.admin_setup import create_super_admin, validate_admin_configuration

logger = get_logger(__name__, "main.log")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("🚀 Запуск додатка...")

    try:
        DatabaseConnection.connect()

        if not validate_admin_configuration():
            raise ValueError("Невірна конфігурація супер адміна")

        create_super_admin()

        from backend.utils.cvat_setup import initialize_default_cvat_settings
        initialize_default_cvat_settings()

        logger.info("✅ Ініціалізація завершена")
    except Exception as e:
        logger.error(f"❌ Помилка ініціалізації: {str(e)}")

    yield

    DatabaseConnection.disconnect()
    logger.info("🛑 Завершення роботи додатка")


app = FastAPI(
    title="Video Annotation API",
    description="API для завантаження, анотування та обробки відео з авторизацією",
    version="1.0.0",
    lifespan=lifespan
)

app.middleware("http")(log_middleware)
app.middleware("http")(auth_middleware)

app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

if os.path.exists("frontend/static"):
    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
    logger.info("Статичні файли змонтовано з директорії 'frontend/static'")
elif os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")
    logger.info("Статичні файли змонтовано з директорії 'frontend'")
else:
    logger.warning("Директорія 'frontend' не знайдена")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(video.router)
app.include_router(annotation.router)
app.include_router(static.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "video-annotation-api"}


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    logger.info(f"MongoDB URI: {settings.mongo_uri}")
    logger.info(f"Запуск сервера на {settings.fast_api_host}:{settings.fast_api_port}")

    uvicorn.run(
        "backend.main:app",
        host=settings.fast_api_host,
        port=settings.fast_api_port,
        reload=settings.reload,
        log_level="info"
    )