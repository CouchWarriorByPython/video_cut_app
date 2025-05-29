from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Dict, Any
import os
from bson import json_util
from datetime import datetime

from tasks import process_video_annotation
from db_connector import create_repository
from utils.celery_utils import get_default_cvat_project_params, parse_azure_blob_url, get_blob_service_client, \
    download_blob_to_local
from configs import Settings
from utils.logger import get_logger
from schemas import (
    VideoUploadRequest, VideoUploadResponse, ErrorResponse,
    SaveFragmentsRequest, SaveFragmentsResponse,
    VideoListResponse, GetAnnotationResponse,
    VideoAnnotationResponse, ValidationErrorResponse,
    VideoMetadataResponse, CVATProjectParamsResponse, ClipInfoResponse
)

logger = get_logger(__name__)

app = FastAPI(
    title="Video Annotation API",
    description="API для завантаження, анотування та обробки відео",
    version="1.0.0"
)

JSON_OPTIONS = json_util.JSONOptions(json_mode=json_util.JSONMode.RELAXED)
os.makedirs(Settings.temp_folder, exist_ok=True)

templates = Jinja2Templates(directory="front")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обробник помилок валідації Pydantic"""
    errors = []
    for error in exc.errors():
        field_name = '.'.join(str(x) for x in error['loc'][1:]) if len(error['loc']) > 1 else 'unknown'
        errors.append({
            "field": field_name,
            "error": error['msg'],
            "input": error.get('input')
        })

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Помилка валідації даних",
            "errors": errors
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Обробник HTTP помилок"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "error": f"HTTP {exc.status_code}"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник загальних помилок"""
    logger.error(f"Необроблена помилка: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Внутрішня помилка сервера",
            "error": str(exc)
        }
    )


def get_local_video_path(filename: str) -> str:
    """Конструює локальний шлях для відео файлу"""
    local_videos_dir = os.path.join(Settings.temp_folder, "source_videos")
    return os.path.join(local_videos_dir, filename)


def validate_azure_url(url: str) -> Dict[str, Any]:
    """Валідує Azure blob URL та перевіряє доступність"""
    try:
        blob_info = parse_azure_blob_url(url)

        if blob_info["account_name"] != Settings.azure_storage_account_name:
            return {
                "valid": False,
                "error": f"URL повинен бути з storage account '{Settings.azure_storage_account_name}'"
            }

        blob_service_client = get_blob_service_client()
        blob_client = blob_service_client.get_blob_client(
            container=blob_info["container_name"],
            blob=blob_info["blob_name"]
        )

        if not blob_client.exists():
            return {
                "valid": False,
                "error": "Файл не знайдено в Azure Storage"
            }

        properties = blob_client.get_blob_properties()
        filename = os.path.basename(blob_info["blob_name"])

        return {
            "valid": True,
            "filename": filename,
            "content_type": properties.content_settings.content_type or "video/mp4",
            "blob_info": blob_info
        }

    except Exception as e:
        logger.error(f"Помилка валідації Azure URL {url}: {str(e)}")
        return {
            "valid": False,
            "error": f"Помилка валідації URL: {str(e)}"
        }


def convert_db_annotation_to_response(annotation: Dict[str, Any]) -> VideoAnnotationResponse:
    """Конвертує анотацію з БД у response модель"""
    metadata = None
    if annotation.get("metadata"):
        metadata = VideoMetadataResponse(**annotation["metadata"])

    clips = {}
    if annotation.get("clips"):
        for project, project_clips in annotation["clips"].items():
            clips[project] = [ClipInfoResponse(**clip) for clip in project_clips]

    cvat_params = {}
    if annotation.get("cvat_params"):
        for project, params in annotation["cvat_params"].items():
            cvat_params[project] = CVATProjectParamsResponse(**params)

    return VideoAnnotationResponse(
        _id=annotation["_id"],
        azure_link=annotation["azure_link"],
        filename=annotation["filename"],
        content_type=annotation["content_type"],
        created_at=annotation["created_at"],
        updated_at=annotation["updated_at"],
        when=annotation.get("when"),
        where=annotation.get("where"),
        status=annotation["status"],
        metadata=metadata,
        clips=clips,
        cvat_params=cvat_params
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Головна сторінка завантаження відео"""
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/annotator", response_class=HTMLResponse)
async def annotator(request: Request) -> HTMLResponse:
    """Сторінка анотування відео"""
    return templates.TemplateResponse("annotator.html", {"request": request})


@app.get("/styles.css")
async def serve_css() -> FileResponse:
    """Статичний CSS файл"""
    return FileResponse("front/styles.css", media_type="text/css")


@app.get("/upload.js")
async def serve_upload_js() -> FileResponse:
    """Статичний JS файл для завантаження"""
    return FileResponse("front/upload.js", media_type="application/javascript")


@app.get("/annotator.js")
async def serve_annotator_js() -> FileResponse:
    """Статичний JS файл для анотування"""
    return FileResponse("front/annotator.js", media_type="application/javascript")


@app.get("/favicon.ico")
async def serve_favicon():
    """Іконка сайту - заглушка"""
    return Response(status_code=204)


@app.get("/get_video")
async def get_video(azure_link: str) -> FileResponse:
    """Відображає локальне відео для анотування"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            raise HTTPException(status_code=404, detail="Відео не знайдено")

        filename = annotation.get("filename")
        if not filename:
            raise HTTPException(status_code=404, detail="Назва файлу не знайдена")

        local_path = get_local_video_path(filename)

        if not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail="Локальний файл не знайдено")

        return FileResponse(
            path=local_path,
            media_type="video/mp4",
            filename=filename,
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка відображення відео: {str(e)}")
        raise HTTPException(status_code=500, detail="Помилка відображення відео")
    finally:
        if repo:
            repo.close()


@app.post("/upload", response_model=VideoUploadResponse, responses={
    400: {"model": ErrorResponse},
    422: {"model": ValidationErrorResponse},
    500: {"model": ErrorResponse}
})
async def upload(data: VideoUploadRequest) -> VideoUploadResponse:
    """Реєстрація відео за Azure URL з локальним завантаженням"""
    repo = None
    try:
        validation_result = validate_azure_url(data.video_url)

        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Невірний Azure URL: {validation_result['error']}"
            )

        filename = validation_result["filename"]
        local_path = get_local_video_path(filename)

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        download_result = download_blob_to_local(data.video_url, local_path)

        if not download_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Помилка завантаження відео: {download_result['error']}"
            )

        video_record = {
            "azure_link": data.video_url,
            "filename": filename,
            "content_type": validation_result["content_type"],
            "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "when": data.when,
            "where": data.where,
            "status": "not_annotated"
        }

        repo = create_repository(collection_name="source_videos")
        repo.create_indexes()
        record_id = repo.save_annotation(video_record)

        logger.info(f"Відео завантажено локально: {local_path}")

        return VideoUploadResponse(
            _id=record_id,
            azure_link=data.video_url,
            filename=filename,
            message="Відео успішно зареєстровано та завантажено локально"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка при обробці запиту: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка при обробці запиту: {str(e)}")
    finally:
        if repo:
            repo.close()


@app.get("/get_videos", response_model=VideoListResponse, responses={
    500: {"model": ErrorResponse}
})
async def get_videos() -> VideoListResponse:
    """Отримання списку відео які ще не анотовані"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        videos_data = repo.get_all_annotations(filter_query={"status": {"$ne": "annotated"}})

        videos = [convert_db_annotation_to_response(video) for video in videos_data]

        return VideoListResponse(videos=videos)
    except Exception as e:
        logger.error(f"Помилка при отриманні списку відео: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if repo:
            repo.close()


@app.get("/get_annotation", response_model=GetAnnotationResponse, responses={
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def get_annotation(azure_link: str) -> GetAnnotationResponse:
    """Отримання існуючої анотації для відео"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        annotation_data = repo.get_annotation(azure_link)

        if not annotation_data:
            raise HTTPException(
                status_code=404,
                detail=f"Анотацію для відео '{azure_link}' не знайдено"
            )

        annotation = convert_db_annotation_to_response(annotation_data)
        return GetAnnotationResponse(annotation=annotation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка при отриманні анотації: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if repo:
            repo.close()


@app.post("/save_fragments", response_model=SaveFragmentsResponse, responses={
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ValidationErrorResponse},
    500: {"model": ErrorResponse}
})
async def save_fragments(data: SaveFragmentsRequest) -> SaveFragmentsResponse:
    """Збереження фрагментів відео та метаданих"""
    repo = None
    try:
        json_data = data.data
        skip_processing = json_data.get("metadata", {}).get("skip", False)

        repo = create_repository(collection_name="source_videos")
        repo.create_indexes()

        existing = repo.get_annotation(data.azure_link)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Відео з посиланням {data.azure_link} не знайдено"
            )

        clips = json_data.get("clips", {})
        for project_type, project_clips in clips.items():
            for clip in project_clips:
                start_parts = clip["start_time"].split(":")
                end_parts = clip["end_time"].split(":")

                start_seconds = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + int(start_parts[2])
                end_seconds = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + int(end_parts[2])

                if end_seconds - start_seconds < 1:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Мінімальна тривалість кліпу - 1 секунда. Кліп {clip['id']} в проєкті {project_type} занадто короткий."
                    )

        existing.update({
            "metadata": json_data.get("metadata"),
            "clips": json_data.get("clips"),
            "status": "annotated",
            "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
        })

        if "cvat_params" not in existing or not existing["cvat_params"]:
            cvat_params = {}
            for clip_type in json_data.get("clips", {}).keys():
                cvat_params[clip_type] = get_default_cvat_project_params(clip_type)
            existing["cvat_params"] = cvat_params

        record_id = repo.save_annotation(existing)

        task_id = None
        if not skip_processing:
            task_result = process_video_annotation.delay(data.azure_link)
            task_id = task_result.id
            success_message = "Дані успішно збережено. Запущено задачу обробки."
            logger.info(f"Запущено обробку для відео: {data.azure_link}, task_id: {task_id}")
        else:
            success_message = "Дані успішно збережено. Обробку пропущено (skip)."
            logger.info(f"Відео пропущено (skip): {data.azure_link}")

        return SaveFragmentsResponse(
            _id=record_id,
            task_id=task_id,
            message=success_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка при збереженні в MongoDB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if repo:
            repo.close()


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Тимчасова папка: {os.path.abspath(Settings.temp_folder)}")
    logger.info(f"Запуск сервера на {Settings.host}:{Settings.port}")

    uvicorn.run("main:app", host=Settings.host, port=Settings.port, reload=Settings.reload)