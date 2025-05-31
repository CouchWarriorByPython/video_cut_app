import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.exceptions import (
    validation_exception_handler, http_exception_handler, general_exception_handler
)
from backend.api.endpoints import video, annotation, static
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Video Annotation API",
    description="API для завантаження, анотування та обробки відео",
    version="1.0.0"
)

# Реєстрація обробників помилок
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Монтування статичних файлів
if os.path.exists("front"):
    app.mount("/static", StaticFiles(directory="front"), name="static")
    logger.info("Статичні файли змонтовано з директорії 'front'")
else:
    logger.warning("Директорія 'front' не знайдена")

# Підключення роутерів
app.include_router(video.router)
app.include_router(annotation.router)
app.include_router(static.router)

# Створення необхідних директорій
os.makedirs(Settings.temp_folder, exist_ok=True)

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Завантажено конфігурацію: HOST={Settings.host}, PORT={Settings.port}")
    logger.info(f"Тимчасова папка: {os.path.abspath(Settings.temp_folder)}")
    logger.info(f"MongoDB URI: {Settings.mongo_uri}")
    logger.info(f"Запуск сервера на {Settings.host}:{Settings.port}")

    uvicorn.run(
        "backend.main:app",
        host=Settings.host,
        port=Settings.port,
        reload=Settings.reload,
        log_level="info"
    )