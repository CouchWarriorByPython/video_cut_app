from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uvicorn

app = FastAPI(title="Mock Video Server")

# Шлях до відеофайлу
VIDEO_FILENAME = "20250502-1628-IN_Recording.mp4"
VIDEO_PATH = os.path.join(os.path.dirname(__file__), VIDEO_FILENAME)

# Імітуємо Azure URL
base_url = "http://localhost:8001"


class VideoInfo(BaseModel):
    url: str
    filename: str
    content_type: str
    size: int


@app.get("/", response_model=VideoInfo)
async def get_video_info():
    """Повертає інформацію про відеофайл"""
    if not os.path.exists(VIDEO_PATH):
        raise HTTPException(404, detail=f"Файл {VIDEO_FILENAME} не знайдено")

    return VideoInfo(
        url=f"{base_url}/video",
        filename=VIDEO_FILENAME,
        content_type="video/mp4",
        size=os.path.getsize(VIDEO_PATH)
    )


@app.get("/video")
async def serve_video():
    """Повертає відеофайл"""
    if not os.path.exists(VIDEO_PATH):
        raise HTTPException(404, detail=f"Файл {VIDEO_FILENAME} не знайдено")

    return FileResponse(
        VIDEO_PATH,
        media_type="video/mp4",
        filename=VIDEO_FILENAME
    )


if __name__ == "__main__":
    # Перевіряємо наявність файлу
    if not os.path.exists(VIDEO_PATH):
        print(f"ПОМИЛКА: Файл {VIDEO_FILENAME} не знайдено в {os.path.dirname(__file__)}")
        print("Переконайтеся, що файл знаходиться в тій же папці, що і скрипт")
        exit(1)

    print(f"Файл {VIDEO_FILENAME} знайдено, розмір: {os.path.getsize(VIDEO_PATH) / 1024 / 1024:.2f} МБ")
    print(f"Відео буде доступне за адресою: {base_url}/video")

    uvicorn.run("mock_video_server:app", host="localhost", port=8001, reload=False)