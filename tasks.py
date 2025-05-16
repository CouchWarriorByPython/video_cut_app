from typing import Any, Dict
from celery import Celery
from db_connector import create_repository
import json

# Створюємо екземпляр Celery
app = Celery('tasks')

# Завантажуємо конфігурацію з файлу
app.config_from_object('celery_config')


@app.task(name="process_task")
def process_task(param1: str, param2: str) -> Dict[str, Any]:
    """
    Проста задача, що приймає два параметри та повертає результат

    Args:
        param1: Перший параметр
        param2: Другий параметр

    Returns:
        Dict з результатом виконання
    """
    # Тут буде логіка обробки параметрів
    result = {
        "status": "ok",
        "params": {
            "param1": param1,
            "param2": param2
        }
    }

    return result


@app.task(name="process_video_annotation")
def process_video_annotation(source: str) -> Dict[str, Any]:
    """
    Задача для обробки анотацій відео

    Args:
        source: Ідентифікатор відео

    Returns:
        Dict з даними анотації
    """
    try:
        # Створюємо синхронний репозиторій (для Celery)
        repo = create_repository(collection_name="анотації_соурс_відео", async_mode=False)

        # Отримуємо дані з MongoDB
        annotation = repo.get_annotation(source)

        if not annotation:
            return {
                "status": "error",
                "message": f"Анотацію для відео '{source}' не знайдено"
            }

        # Виводимо дані для логування
        print(f"Отримано дані для відео '{source}':")
        print(json.dumps(annotation, indent=2, ensure_ascii=False))

        return {
            "status": "ok",
            "source": source,
            "annotation": annotation
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        # Закриваємо з'єднання
        repo.close()