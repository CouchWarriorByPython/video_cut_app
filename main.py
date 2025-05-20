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

# Директорії для відео
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
async def upload(data: VideoUploadRequest):
    """Реєстрація відео за URL і його завантаження"""
    try:
        azure_link = data.video_url.strip()

        if not azure_link:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "URL відео не вказано"}
            )

        print(f"Запит на завантаження відео: {azure_link}")

        # Перевіряємо чи URL дійсний
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(azure_link)
            if not parsed_url.scheme or not parsed_url.netloc:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"Недійсний URL: {azure_link}"}
                )
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"Помилка при парсингу URL: {str(e)}"}
            )

        # Завантажуємо відео з URL
        download_result = download_video_from_azure(azure_link, UPLOAD_FOLDER)

        if not download_result["success"]:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"Помилка завантаження відео: {download_result['error']}"}
            )

        # Отримуємо локальний шлях для доступу до відео
        local_path = download_result["local_path"]
        filename = download_result["filename"]
        extension = download_result["extension"]

        # Записуємо в MongoDB
        video_record = {
            "azure_link": azure_link,
            "local_path": local_path,
            "extension": extension,
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

        return JSONResponse(
            content={
                "success": True,
                "id": record_id,
                "azure_link": azure_link,
                "local_path": local_path,  # Виправлена змінна, було local_url
                "filename": filename,
                "message": "Відео успішно завантажено та додано до бази даних"
            }
        )

    except Exception as e:
        import traceback
        print(f"Помилка при обробці запиту: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Помилка при обробці запиту: {str(e)}"}
        )
    finally:
        if 'repo' in locals():
            repo.close()


@app.get("/get_videos")
async def get_videos():
    """Отримання списку всіх відео для анотування"""
    try:
        repo = create_repository(collection_name="анотації_соурс_відео")
        videos = repo.get_all_annotations()

        print(f"Знайдено {len(videos)} відео в базі даних")

        video_list = []
        for video in videos:
            # Логуємо кожен запис для відстеження
            video_id = str(video.get("_id"))
            azure_link = video.get("azure_link")
            local_path = video.get("local_path", video.get("local_url", ""))

            print(f"Обробка відео #{video_id}: {azure_link}, local_path={local_path}")

            video_list.append({
                "id": video_id,
                "azure_link": azure_link,
                "local_path": local_path,
                "extension": video.get("extension", "mp4"),
                "created_at": video.get("created_at", datetime.utcnow()).isoformat(),
                "where": video.get("where"),
                "when": video.get("when"),
                "status": video.get("status", "not_annotated")
            })

        return {
            "success": True,
            "videos": video_list
        }
    except Exception as e:
        print(f"Помилка при отриманні списку відео: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if 'repo' in locals():
            repo.close()

@app.get("/get_annotation")
async def get_annotation(azure_link: str):
    """Отримання існуючої анотації для відео"""
    try:
        repo = create_repository(collection_name="анотації_соурс_відео")
        annotation = repo.get_annotation(azure_link)

        if annotation:
            # Конвертуємо документ MongoDB у JSON
            # Оскільки деякі типи MongoDB (ObjectId, datetime) не серіалізуються напряму
            from bson import json_util
            annotation_json = json.loads(json_util.dumps(annotation))

            return {
                "success": True,
                "annotation": annotation_json
            }
        else:
            return {
                "success": False,
                "message": f"Анотацію для відео '{azure_link}' не знайдено"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
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


if __name__ == "__main__":
    import uvicorn

    print(f"Папка для відео: {os.path.abspath(UPLOAD_FOLDER)}")
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)