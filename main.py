from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
import os
import json
import shutil
from pydantic import BaseModel

from tasks import process_video_annotation
from db_connector import create_repository
from utils.cvat_cli import get_cvat_task_parameters
from datetime import datetime
from utils.azure_downloader import download_video_from_azure

app = FastAPI()

# Створення необхідних директорій
UPLOAD_FOLDER = "source_videos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Роздаємо відео з папки source_videos
app.mount("/videos", StaticFiles(directory=UPLOAD_FOLDER), name="videos")

# Підключення шаблонів для рендерингу
templates = Jinja2Templates(directory="front")


def format_date_for_human(date_obj: datetime) -> str:
    """Форматує дату у зручний для читання вигляд"""
    return date_obj.strftime("%d.%m.%Y %H:%M")


# Маршрут для головної сторінки (тепер це uploader)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


# Маршрут для сторінки анотатора
@app.get("/annotator", response_class=HTMLResponse)
async def annotator(request: Request):
    return templates.TemplateResponse("annotator.html", {"request": request})


# Маршрут для обслуговування CSS
@app.get("/styles.css")
async def serve_css():
    return FileResponse("front/styles.css", media_type="text/css")


# Маршрут для обслуговування JavaScript файлів
@app.get("/upload.js")
async def serve_upload_js():
    return FileResponse("front/upload.js", media_type="application/javascript")


@app.get("/annotator.js")
async def serve_annotator_js():
    return FileResponse("front/annotator.js", media_type="application/javascript")


# Завантаження відео через drag-and-drop
@app.post("/upload")
async def upload_file(video: UploadFile = File(...)):
    if not video:
        raise HTTPException(status_code=400, detail="Відео не знайдено")

    if video.filename == "":
        raise HTTPException(status_code=400, detail="Файл не вибрано")

    # Зберігаємо з оригінальною назвою
    filename = video.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # Додаємо суфікс, якщо файл з такою назвою вже існує
    base_name, extension = os.path.splitext(filename)
    counter = 1
    while os.path.exists(filepath):
        filename = f"{base_name}_{counter}{extension}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        counter += 1

    # Зберігаємо файл
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    # Створюємо запис у MongoDB з заглушкою для URL
    video_name = base_name
    video_record = {
        "source": video_name,
        "azure_path": "local_upload",  # Заглушка для поля посилання
        "extension": extension,
        "upload_date": format_date_for_human(datetime.now()),
        "status": "not_annotated"
    }

    try:
        repo = create_repository(collection_name="анотації_соурс_відео")
        repo.create_indexes()
        repo.save_annotation(video_record)
    except Exception as e:
        print(f"Помилка при збереженні в MongoDB: {str(e)}")
    finally:
        if 'repo' in locals():
            repo.close()

    return {
        "success": True,
        "filename": filename,
        "source": video_name,
        "path": f"/videos/{filename}"
    }


# Схема даних для запиту на завантаження
class VideoUploadRequest(BaseModel):
    video_url: str
    where: Optional[str] = None
    when: Optional[str] = None


@app.post("/upload_from_azure")
async def upload_from_azure(data: VideoUploadRequest):
    try:
        # Викликаємо заглушку для завантаження відео з Azure
        result = download_video_from_azure(data.video_url)

        if not result["success"]:
            return {
                "success": False,
                "message": f"Помилка при завантаженні відео: {result['error']}"
            }

        # Формуємо запис для MongoDB
        source = result["source"]
        azure_path = result["azure_path"]
        extension = result["extension"]

        video_record = {
            "source": source,
            "azure_path": azure_path,
            "extension": extension,
            "upload_date": format_date_for_human(datetime.now()),
            "status": "not_annotated"
        }

        # Додаємо опційні поля
        if data.where:
            video_record["where"] = data.where

        if data.when:
            video_record["when"] = data.when

        # Зберігаємо в MongoDB
        repo = create_repository(collection_name="анотації_соурс_відео")
        repo.create_indexes()
        save_result = repo.save_annotation(video_record)

        return {
            "success": True,
            "message": "Відео успішно завантажено та додано до бази даних",
            "source": source,
            "db_result": save_result
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Помилка при обробці запиту: {str(e)}"
        }
    finally:
        if 'repo' in locals():
            repo.close()


# Збереження фрагментів у JSON
@app.post("/save_fragments")
async def save_fragments(data: Dict[str, Any]):
    video_name = data.get("video_name", "unknown")
    json_data = data.get("data", {})

    try:
        # Додаємо параметри CVAT для кожного проєкту
        cvat_params = get_cvat_task_parameters()
        json_data["cvat_params"] = cvat_params

        # Зберігаємо дані в MongoDB
        repo = create_repository(collection_name="анотації_соурс_відео")
        # Переконуємося що індекси створено
        repo.create_indexes()
        repo.save_annotation(json_data)

        # Запускаємо Celery задачу
        task_result = process_video_annotation.delay(json_data["source"])

        # Виводимо в термінал запис з бази для перевірки
        print(f"Збережено анотацію для відео '{json_data['source']}':")
        print(json.dumps(json_data, indent=2, ensure_ascii=False))

        return {
            "success": True,
            "task_id": task_result.id
        }
    except Exception as e:
        print(f"Помилка при збереженні в MongoDB: {str(e)}")
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        if 'repo' in locals():
            repo.close()


# Отримання списку відео для анотування
@app.get("/get_videos")
async def get_videos():
    try:
        repo = create_repository(collection_name="анотації_соурс_відео")
        videos = repo.get_all_annotations()

        video_list = []
        for video in videos:
            # Перетворюємо MongoDB документ в Python dict
            source = video.get("source", "")
            extension = video.get("extension", ".mp4")

            video_list.append({
                "source": source,
                "filename": f"{source}{extension}",
                "upload_date": video.get("upload_date", ""),
                "where": video.get("where", ""),
                "when": video.get("when", "")
            })

        return {
            "success": True,
            "videos": video_list
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if 'repo' in locals():
            repo.close()


# Для запуску сервера
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=8000, reload=True)