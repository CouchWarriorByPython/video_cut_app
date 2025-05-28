from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
import os
import json
from pydantic import BaseModel
from bson import json_util
from datetime import datetime

from tasks import process_video_annotation
from db_connector import create_repository
from utils.celery_utils import get_default_cvat_project_params, parse_azure_blob_url, get_blob_service_client, \
    download_blob_to_local
from configs import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI()

JSON_OPTIONS = json_util.JSONOptions(json_mode=json_util.JSONMode.RELAXED)
os.makedirs(Settings.temp_folder, exist_ok=True)

templates = Jinja2Templates(directory="front")


def json_response(content: Any) -> JSONResponse:
    """Створює JSON відповідь з плоским форматуванням MongoDB документів"""
    json_str = json_util.dumps(content, json_options=JSON_OPTIONS)
    return JSONResponse(content=json.loads(json_str))


def get_local_video_path(filename: str) -> str:
    """Конструює локальний шлях для відео файлу"""
    local_videos_dir = os.path.join(Settings.temp_folder, "source_videos")
    return os.path.join(local_videos_dir, filename)


class VideoUploadRequest(BaseModel):
    """Модель для запиту завантаження відео"""
    video_url: str
    where: Optional[str] = None
    when: Optional[str] = None


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
            "size": properties.size,
            "content_type": properties.content_settings.content_type or "video/mp4",
            "blob_info": blob_info
        }

    except Exception as e:
        logger.error(f"Помилка валідації Azure URL {url}: {str(e)}")
        return {
            "valid": False,
            "error": f"Помилка валідації URL: {str(e)}"
        }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/annotator", response_class=HTMLResponse)
async def annotator(request: Request):
    return templates.TemplateResponse("annotator.html", {"request": request})


@app.get("/styles.css")
async def serve_css():
    return FileResponse("front/styles.css", media_type="text/css")


@app.get("/upload.js")
async def serve_upload_js():
    return FileResponse("front/upload.js", media_type="application/javascript")


@app.get("/annotator.js")
async def serve_annotator_js():
    return FileResponse("front/annotator.js", media_type="application/javascript")


@app.get("/get_video")
async def get_video(azure_link: str):
    """Відображає локальне відео для анотування"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            raise HTTPException(404, detail="Відео не знайдено")

        filename = annotation.get("filename")
        if not filename:
            raise HTTPException(404, detail="Назва файлу не знайдена")

        local_path = get_local_video_path(filename)

        if not os.path.exists(local_path):
            raise HTTPException(404, detail="Локальний файл не знайдено")

        return FileResponse(
            path=local_path,
            media_type="video/mp4",
            filename=filename,
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600"
            }
        )

    except Exception as e:
        logger.error(f"Помилка відображення відео: {str(e)}")
        raise HTTPException(500, detail="Помилка відображення відео")
    finally:
        if repo:
            repo.close()


@app.post("/upload")
async def upload(data: VideoUploadRequest) -> JSONResponse:
    """Реєстрація відео за Azure URL з локальним завантаженням"""
    repo = None
    try:
        azure_link = data.video_url.strip()

        if not azure_link:
            return json_response({"success": False, "message": "URL відео не вказано"})

        validation_result = validate_azure_url(azure_link)

        if not validation_result["valid"]:
            return json_response({
                "success": False,
                "message": f"Невірний Azure URL: {validation_result['error']}"
            })

        filename = validation_result["filename"]
        local_path = get_local_video_path(filename)

        # Створюємо директорію якщо не існує
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Завантажуємо відео локально
        download_result = download_blob_to_local(azure_link, local_path)

        if not download_result["success"]:
            return json_response({
                "success": False,
                "message": f"Помилка завантаження відео: {download_result['error']}"
            })

        video_record = {
            "azure_link": azure_link,
            "filename": filename,
            "size": validation_result["size"],
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

        return json_response({
            "success": True,
            "_id": record_id,
            "azure_link": azure_link,
            "filename": filename,
            "message": "Відео успішно зареєстровано та завантажено локально"
        })

    except Exception as e:
        logger.error(f"Помилка при обробці запиту: {str(e)}")
        return json_response({"success": False, "message": f"Помилка при обробці запиту: {str(e)}"})
    finally:
        if repo:
            repo.close()


@app.get("/get_videos")
async def get_videos() -> JSONResponse:
    """Отримання списку відео які ще не анотовані"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        videos = repo.get_all_annotations(filter_query={"status": {"$ne": "annotated"}})

        return json_response({
            "success": True,
            "videos": videos
        })
    except Exception as e:
        logger.error(f"Помилка при отриманні списку відео: {str(e)}")
        return json_response({"success": False, "error": str(e)})
    finally:
        if repo:
            repo.close()


@app.get("/get_annotation")
async def get_annotation(azure_link: str) -> JSONResponse:
    """Отримання існуючої анотації для відео"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        annotation = repo.get_annotation(azure_link)

        if annotation:
            return json_response({
                "success": True,
                "annotation": annotation
            })
        else:
            return json_response({
                "success": False,
                "message": f"Анотацію для відео '{azure_link}' не знайдено"
            })
    except Exception as e:
        logger.error(f"Помилка при отриманні анотації: {str(e)}")
        return json_response({"success": False, "error": str(e)})
    finally:
        if repo:
            repo.close()


@app.post("/save_fragments")
async def save_fragments(data: Dict[str, Any]) -> JSONResponse:
    """Збереження фрагментів відео та метаданих"""
    azure_link = data.get("azure_link")
    json_data = data.get("data", {})
    skip_processing = json_data.get("metadata", {}).get("skip", False)

    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        repo.create_indexes()

        existing = repo.get_annotation(azure_link)
        if not existing:
            return json_response({
                "success": False,
                "error": f"Відео з посиланням {azure_link} не знайдено"
            })

        # Валідація тривалості кліпів
        clips = json_data.get("clips", {})
        for project_type, project_clips in clips.items():
            for clip in project_clips:
                start_parts = clip["start_time"].split(":")
                end_parts = clip["end_time"].split(":")

                start_seconds = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + int(start_parts[2])
                end_seconds = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + int(end_parts[2])

                if end_seconds - start_seconds < 1:
                    return json_response({
                        "success": False,
                        "error": f"Мінімальна тривалість кліпу - 1 секунда. Кліп {clip['id']} в проєкті {project_type} занадто короткий."
                    })

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
            task_result = process_video_annotation.delay(azure_link)
            task_id = task_result.id
            success_message = "Дані успішно збережено. Запущено задачу обробки."
            logger.info(f"Запущено обробку для відео: {azure_link}, task_id: {task_id}")
        else:
            success_message = "Дані успішно збережено. Обробку пропущено (skip)."
            logger.info(f"Відео пропущено (skip): {azure_link}")

        return json_response({
            "success": True,
            "_id": record_id,
            "task_id": task_id,
            "message": success_message
        })

    except Exception as e:
        logger.error(f"Помилка при збереженні в MongoDB: {str(e)}")
        return json_response({"success": False, "error": str(e)})
    finally:
        if repo:
            repo.close()


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Тимчасова папка: {os.path.abspath(Settings.temp_folder)}")
    logger.info(f"Запуск сервера на {Settings.host}:{Settings.port}")

    uvicorn.run("main:app", host=Settings.host, port=Settings.port, reload=Settings.reload)