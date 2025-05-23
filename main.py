from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
import os
import json
from pydantic import BaseModel
from bson import json_util
from datetime import datetime

from tasks import process_video_annotation, monitor_clip_tasks
from db_connector import create_repository
from utils.celery_utils import get_cvat_task_parameters, download_video_from_azure
from configs import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI()

# Налаштування json_util для отримання плоского представлення
JSON_OPTIONS = json_util.JSONOptions(json_mode=json_util.JSONMode.RELAXED)

# Створюємо необхідні директорії
os.makedirs(Settings.upload_folder, exist_ok=True)

app.mount("/videos", StaticFiles(directory=Settings.upload_folder), name="videos")
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


@app.post("/upload")
async def upload(data: VideoUploadRequest) -> JSONResponse:
    """Реєстрація відео за URL і його завантаження"""
    repo = None
    try:
        azure_link = data.video_url.strip()

        if not azure_link:
            return json_response({"success": False, "message": "URL відео не вказано"})

        # Завантажуємо відео з URL
        download_result = download_video_from_azure(azure_link, Settings.upload_folder)

        if not download_result["success"]:
            return json_response({
                "success": False,
                "message": f"Помилка завантаження відео: {download_result['error']}"
            })

        # Записуємо в MongoDB
        video_record = {
            "azure_link": azure_link,
            "local_path": download_result["local_path"],
            "extension": download_result["extension"],
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "when": data.when,
            "where": data.where,
            "status": "not_annotated"
        }

        # Зберігаємо запис у MongoDB
        repo = create_repository(collection_name="анотації_соурс_відео")
        repo.create_indexes()
        record_id = repo.save_annotation(video_record)

        logger.info(f"Відео успішно завантажено: {azure_link}")

        return json_response({
            "success": True,
            "id": record_id,
            "azure_link": azure_link,
            "local_path": download_result["local_path"],
            "filename": download_result["filename"],
            "message": "Відео успішно завантажено та додано до бази даних"
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
        repo = create_repository(collection_name="анотації_соурс_відео")
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
        repo = create_repository(collection_name="анотації_соурс_відео")
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
        repo = create_repository(collection_name="анотації_соурс_відео")
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
            "updated_at": datetime.utcnow()
        })

        # Отримуємо параметри CVAT для кліпів
        all_params = get_cvat_task_parameters()
        cvat_params = {
            clip_type: all_params[clip_type]
            for clip_type in json_data.get("clips", {}).keys()
            if clip_type in all_params
        }

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

    logger.info(f"Папка для відео: {os.path.abspath(Settings.upload_folder)}")
    logger.info(f"Запуск сервера на {Settings.host}:{Settings.port}")

    uvicorn.run("main:app", host=Settings.host, port=Settings.port, reload=Settings.reload)