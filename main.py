from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Body
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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

UPLOAD_FOLDER = "source_videos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.mount("/videos", StaticFiles(directory=UPLOAD_FOLDER), name="videos")
templates = Jinja2Templates(directory="front")


def format_date_for_human(date_obj: datetime) -> str:
    """Форматує дату у зручний для читання вигляд"""
    return date_obj.strftime("%d.%m.%Y %H:%M")


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
    video_url: str
    where: Optional[str] = None
    when: Optional[str] = None


@app.post("/upload")
async def upload(request: Request):
    """Універсальний ендпоінт для завантаження відео"""
    content_type = request.headers.get("content-type", "")

    try:
        if "multipart/form-data" in content_type:
            # Обробка завантаження файлу
            form = await request.form()
            video = form.get("video")
            where = form.get("where")
            when = form.get("when")

            if not video or not hasattr(video, "filename") or video.filename == "":
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Файл не вибрано"}
                )

            filename = video.filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)

            base_name, extension = os.path.splitext(filename)
            counter = 1
            while os.path.exists(filepath):
                filename = f"{base_name}_{counter}{extension}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                counter += 1

            # Зберігаємо файл
            file_content = await video.read()
            with open(filepath, "wb") as buffer:
                buffer.write(file_content)

            # Формуємо повний URI до файлу
            server_url = request.base_url
            azure_link = f"{server_url}videos/{filename}"

            # Записуємо в MongoDB
            video_record = {
                "azure_link": azure_link,
                "extension": extension[1:] if extension.startswith('.') else extension,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "when": when,
                "where": where,
                "status": "not_annotated",
                "metadata": None,
                "clips": {},
                "cvat_params": {}
            }

        elif "application/json" in content_type:
            # Обробка завантаження по URL
            data = await request.json()
            azure_link = data.get("video_url")
            where = data.get("where")
            when = data.get("when")

            if not azure_link:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "URL відео не вказано"}
                )

            # Визначаємо розширення з URL
            extension = os.path.splitext(azure_link)[1]
            if not extension:
                extension = ".mp4"  # За замовчуванням

            # Записуємо в MongoDB
            video_record = {
                "azure_link": azure_link,
                "extension": extension[1:] if extension.startswith('.') else extension,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "when": when,
                "where": where,
                "status": "not_annotated",
                "metadata": None,
                "clips": {},
                "cvat_params": {}
            }

        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Непідтримуваний Content-Type"}
            )

        # Зберігаємо запис у MongoDB
        repo = create_repository(collection_name="анотації_соурс_відео")
        repo.create_indexes()
        record_id = repo.save_annotation(video_record)

        return JSONResponse(
            content={
                "success": True,
                "id": record_id,
                "azure_link": azure_link,
                "message": "Відео успішно завантажено та додано до бази даних"
            }
        )

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Помилка при обробці запиту: {str(e)}"}
        )
    finally:
        if 'repo' in locals():
            repo.close()


@app.post("/save_fragments")
async def save_fragments(data: Dict[str, Any]):
    """Збереження фрагментів відео та метаданих"""
    azure_link = data.get("azure_link")
    json_data = data.get("data", {})

    try:
        repo = create_repository(collection_name="анотації_соурс_відео")
        repo.create_indexes()

        existing = repo.get_annotation(azure_link)

        if existing:
            # Оновлюємо існуючий запис
            existing.update({
                "metadata": json_data.get("metadata"),
                "clips": json_data.get("clips"),
                "status": "annotated",
                "updated_at": datetime.utcnow()
            })

            # Отримуємо параметри CVAT для кліпів
            cvat_params = {}
            all_params = get_cvat_task_parameters()
            for clip_type in json_data.get("clips", {}).keys():
                if clip_type in all_params:
                    cvat_params[clip_type] = all_params[clip_type]

            existing["cvat_params"] = cvat_params

            record_id = repo.save_annotation(existing)
            task_result = process_video_annotation.delay(azure_link)

            return {
                "success": True,
                "id": record_id,
                "task_id": task_result.id
            }
        else:
            return {
                "success": False,
                "error": f"Відео з посиланням {azure_link} не знайдено"
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


@app.get("/get_videos")
async def get_videos():
    """Отримання списку всіх відео для анотування"""
    try:
        repo = create_repository(collection_name="анотації_соурс_відео")
        videos = repo.get_all_annotations()

        video_list = []
        for video in videos:
            video_list.append({
                "id": str(video.get("_id")),
                "azure_link": video.get("azure_link"),
                "extension": video.get("extension", "mp4"),
                "created_at": video.get("created_at", datetime.utcnow()).isoformat(),
                "updated_at": video.get("updated_at", datetime.utcnow()).isoformat(),
                "where": video.get("where"),
                "when": video.get("when"),
                "status": video.get("status", "not_annotated")
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=8000, reload=True)