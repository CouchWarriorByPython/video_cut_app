from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, Any
import os
import json
import shutil
from tasks import process_video_annotation
from db_connector import create_repository

app = FastAPI()

# Створення необхідних директорій
UPLOAD_FOLDER = "source_videos"
JSON_FOLDER = "json_data"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(JSON_FOLDER, exist_ok=True)

# Роздаємо відео з папки source_videos
app.mount("/videos", StaticFiles(directory=UPLOAD_FOLDER), name="videos")

# Підключення шаблонів для рендерингу
templates = Jinja2Templates(directory="front")

# Маршрут для головної сторінки
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Маршрут для обслуговування CSS
@app.get("/styles.css")
async def serve_css():
    return FileResponse("front/styles.css", media_type="text/css")


# Маршрут для обслуговування JavaScript
@app.get("/script.js")
async def serve_js():
    return FileResponse("front/script.js", media_type="application/javascript")


# Завантаження відео
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

    return {
        "success": True,
        "filename": filename,
        "path": f"/videos/{filename}"  # Змінюємо шлях для доступу до відео
    }


# Збереження фрагментів у JSON
@app.post("/save_fragments")
async def save_fragments(data: Dict[str, Any]):
    video_name = data.get("video_name", "unknown")
    json_data = data.get("data", {})

    try:
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

# Для запуску сервера
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=8000, reload=True)