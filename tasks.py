from typing import Any, Dict
from celery import Celery
from db_connector import create_repository
import json
from bson import json_util

# Створюємо екземпляр Celery
app = Celery('tasks')

# Завантажуємо конфігурацію з файлу
app.config_from_object('celery_config')

# Налаштування json_util для отримання плоского представлення
JSON_OPTIONS = json_util.JSONOptions(json_mode=json_util.JSONMode.RELAXED)

@app.task(name="process_video_annotation")
def process_video_annotation(azure_link: str) -> Dict[str, Any]:
    repo = None
    try:
        repo = create_repository(collection_name="анотації_соурс_відео", async_mode=False)
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            return {
                "status": "error",
                "message": f"Анотацію для відео '{azure_link}' не знайдено"
            }

        # Конвертуємо документ у плоску структуру для Celery
        json_str = json_util.dumps(annotation, json_options=JSON_OPTIONS)
        processed_annotation = json.loads(json_str)

        print(f"Отримано дані для відео '{azure_link}':")
        print(json.dumps(processed_annotation, indent=2, ensure_ascii=False))

        return {
            "status": "ok",
            "azure_link": azure_link,
            "annotation": processed_annotation
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        if repo:
            repo.close()