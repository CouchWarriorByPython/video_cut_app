from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
import os
import json
from pydantic import BaseModel
from bson import json_util
from datetime import datetime

from tasks import process_video_annotation, monitor_clip_tasks
from db_connector import create_repository
from utils.celery_utils import get_default_cvat_project_params, parse_azure_blob_url, get_blob_service_client
from configs import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI()

# Налаштування json_util для отримання плоского представлення
JSON_OPTIONS = json_util.JSONOptions(json_mode=json_util.JSONMode.RELAXED)

# Створюємо необхідні директорії
os.makedirs(Settings.temp_folder, exist_ok=True)

templates = Jinja2Templates(directory="front")


def json_response(content: Any) -> JSONResponse:
    """Створює JSON відповідь з плоским форматуванням MongoDB документів"""
    json_str = json_util.dumps(content, json_options=JSON_OPTIONS)
    return JSONResponse(content=json.loads(json_str))


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


class VideoUploadRequest(BaseModel):
    """Модель для запиту завантаження відео"""
    video_url: str
    where: Optional[str] = None
    when: Optional[str] = None


class CVATParametersRequest(BaseModel):
    """Модель для налаштування CVAT параметрів"""
    azure_link: str
    cvat_params: Dict[str, Dict[str, Any]]


def validate_azure_url(url: str) -> Dict[str, Any]:
    """Валідує Azure blob URL та перевіряє доступність"""
    try:
        # Парсимо URL
        blob_info = parse_azure_blob_url(url)

        # Перевіряємо чи це наш storage account
        if blob_info["account_name"] != Settings.azure_storage_account_name:
            return {
                "valid": False,
                "error": f"URL повинен бути з storage account '{Settings.azure_storage_account_name}'"
            }

        # Перевіряємо існування blob
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

        # Отримуємо властивості файлу
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


@app.post("/upload")
async def upload(data: VideoUploadRequest) -> JSONResponse:
    """Реєстрація відео за Azure URL"""
    repo = None
    try:
        azure_link = data.video_url.strip()

        if not azure_link:
            return json_response({"success": False, "message": "URL відео не вказано"})

        # Валідуємо Azure URL
        validation_result = validate_azure_url(azure_link)

        if not validation_result["valid"]:
            return json_response({
                "success": False,
                "message": f"Невірний Azure URL: {validation_result['error']}"
            })

        # Записуємо в MongoDB
        video_record = {
            "azure_link": azure_link,
            "filename": validation_result["filename"],
            "size": validation_result["size"],
            "content_type": validation_result["content_type"],
            "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "when": data.when,
            "where": data.where,
            "status": "not_annotated"
        }

        # Зберігаємо запис у MongoDB
        repo = create_repository(collection_name="source_videos")
        repo.create_indexes()
        record_id = repo.save_annotation(video_record)

        logger.info(f"Відео зареєстровано: {azure_link}")

        return json_response({
            "success": True,
            "id": record_id,
            "azure_link": azure_link,
            "filename": validation_result["filename"],
            "message": "Відео успішно зареєстровано в системі"
        })

    except Exception as e:
        logger.error(f"Помилка при обробці запиту: {str(e)}")
        return json_response({"success": False, "message": f"Помилка при обробці запиту: {str(e)}"})
    finally:
        if repo:
            repo.close()


@app.get("/get_videos")
async def get_videos() -> JSONResponse:
    """Отримання списку всіх відео для анотування"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        videos = repo.get_all_annotations()

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


@app.post("/set_cvat_params")
async def set_cvat_params(data: CVATParametersRequest) -> JSONResponse:
    """Налаштування CVAT параметрів для відео"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")

        existing = repo.get_annotation(data.azure_link)
        if not existing:
            return json_response({
                "success": False,
                "error": f"Відео з посиланням {data.azure_link} не знайдено"
            })

        # Оновлюємо CVAT параметри
        existing["cvat_params"] = data.cvat_params
        existing["updated_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")

        record_id = repo.save_annotation(existing)

        logger.info(f"CVAT параметри оновлено для відео: {data.azure_link}")

        return json_response({
            "success": True,
            "id": record_id,
            "message": "CVAT параметри успішно збережено"
        })

    except Exception as e:
        logger.error(f"Помилка при збереженні CVAT параметрів: {str(e)}")
        return json_response({"success": False, "error": str(e)})
    finally:
        if repo:
            repo.close()


@app.get("/get_cvat_params")
async def get_cvat_params(azure_link: str) -> JSONResponse:
    """Отримання CVAT параметрів для відео"""
    repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            return json_response({
                "success": False,
                "error": f"Відео з посиланням {azure_link} не знайдено"
            })

        # Якщо параметри не встановлені, повертаємо дефолтні
        cvat_params = annotation.get("cvat_params", {})
        if not cvat_params:
            cvat_params = {
                "motion-det": get_default_cvat_project_params("motion-det"),
                "tracking": get_default_cvat_project_params("tracking"),
                "mil-hardware": get_default_cvat_project_params("mil-hardware"),
                "re-id": get_default_cvat_project_params("re-id")
            }

        return json_response({
            "success": True,
            "cvat_params": cvat_params
        })

    except Exception as e:
        logger.error(f"Помилка при отриманні CVAT параметрів: {str(e)}")
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

        # Оновлюємо існуючий запис
        existing.update({
            "metadata": json_data.get("metadata"),
            "clips": json_data.get("clips"),
            "status": "annotated",
            "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
        })

        # Якщо CVAT параметри не встановлені, використовуємо дефолтні
        if "cvat_params" not in existing or not existing["cvat_params"]:
            cvat_params = {}
            for clip_type in json_data.get("clips", {}).keys():
                cvat_params[clip_type] = get_default_cvat_project_params(clip_type)
            existing["cvat_params"] = cvat_params

        record_id = repo.save_annotation(existing)

        # Запускаємо обробку, тільки якщо відео не помічено як "skip"
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
            "id": record_id,
            "task_id": task_id,
            "message": success_message
        })

    except Exception as e:
        logger.error(f"Помилка при збереженні в MongoDB: {str(e)}")
        return json_response({"success": False, "error": str(e)})
    finally:
        if repo:
            repo.close()


@app.get("/clip_processing_status/{task_id}")
async def clip_processing_status(task_id: str) -> JSONResponse:
    """Перевіряє статус обробки кліпів"""
    try:
        # Отримуємо статус задачі
        task = process_video_annotation.AsyncResult(task_id)

        if task.ready():
            result = task.result

            # Якщо задача успішно завершена і є task_ids, перевіряємо статус підзадач
            if task.successful() and isinstance(result, dict) and "task_ids" in result:
                status_task = monitor_clip_tasks.delay(result["task_ids"])
                status_result = status_task.get(timeout=5)  # Чекаємо не більше 5 секунд

                return json_response({
                    "success": True,
                    "main_task_status": task.status,
                    "main_task_result": result,
                    "clips_status": status_result
                })

        return json_response({
            "success": True,
            "status": task.status,
            "result": task.result if task.ready() else None
        })
    except Exception as e:
        logger.error(f"Помилка при перевірці статусу: {str(e)}")
        return json_response({
            "success": False,
            "error": str(e)
        })


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Тимчасова папка: {os.path.abspath(Settings.temp_folder)}")
    logger.info(f"Запуск сервера на {Settings.host}:{Settings.port}")

    uvicorn.run("main:app", host=Settings.host, port=Settings.port, reload=Settings.reload)