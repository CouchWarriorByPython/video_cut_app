from typing import Any, Dict
from celery import Celery
from db_connector import create_repository
import json
from bson import json_util

# Створюємо екземпляр Celery
app = Celery('tasks')

# Завантажуємо конфігурацію з файлу
app.config_from_object('celery_config')

@app.task(name="process_video_annotation")
def process_video_annotation(azure_link: str) -> Dict[str, Any]:
    try:
        repo = create_repository(collection_name="анотації_соурс_відео", async_mode=False)
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            return {
                "status": "error",
                "message": f"Анотацію для відео '{azure_link}' не знайдено"
            }

        # Просте рішення - використати json для конвертації документа
        json_string = json_util.dumps(annotation)
        parsed_document = json.loads(json_string)  # Це поверне звичайні Python об'єкти

        print(f"Отримано дані для відео '{azure_link}':")
        print(json.dumps(parsed_document, indent=2, ensure_ascii=False))

        return {
            "status": "ok",
            "azure_link": azure_link,
            "annotation": parsed_document
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        repo.close()