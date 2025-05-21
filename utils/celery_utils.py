import os
import subprocess
from typing import Dict, Any
import random

# Конфігурація Azure
AZURE_STORAGE_ACCOUNT_NAME = "test_acc"
AZURE_STORAGE_CONTAINER_NAME = "test_container"
AZURE_OUTPUT_PREFIX = "clips"


def format_filename(metadata: Dict[str, Any], original_filename: str, project: str, clip_id: int) -> str:
    """
    Форматує ім'я файлу на основі метаданих

    Формат: uav_type_where_when_original_filename_cutN
    Включає uav_type з метаданих та where/when якщо вони доступні
    """
    # Отримуємо базову назву відео без шляху та розширення
    video_base_name = os.path.splitext(os.path.basename(original_filename))[0]

    # Отримуємо потрібні поля з метаданих
    uav_type = metadata.get("uav_type", "unknown")
    where = metadata.get("where", "")
    when = metadata.get("when", "")

    # Формуємо компоненти імені файлу
    filename_parts = []

    # Додаємо uav_type (обов'язково)
    filename_parts.append(uav_type)

    # Додаємо where та when, якщо вони існують
    if where and where.lower() != "test":
        filename_parts.append(where)
    if when and when != "22222222":
        filename_parts.append(when)

    # Додаємо базову назву файлу та суфікс
    filename_parts.append(f"{video_base_name}_cut{clip_id}")

    # Об'єднуємо всі компоненти через підкреслення
    return "_".join(filename_parts)


def trim_video_clip(
        source_path: str,
        output_path: str,
        start_time: str,
        end_time: str
) -> bool:
    """
    Нарізає відео фрагмент
    """
    try:
        # Виклик ffmpeg для нарізки відео
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            start_time,
            "-to",
            end_time,
            "-i",
            source_path,
            "-c",
            "copy",
            "-loglevel", "error",
            output_path,
        ]
        command_str = " ".join(command)
        print(f"Запуск команди: {command_str}")

        # Виконуємо команду ffmpeg з перехопленням виводу
        result = subprocess.run(command, capture_output=True, text=True)

        # Перевіряємо результат
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            print(f"Помилка при створенні кліпу: {result.stderr}")
            return False
    except Exception as e:
        print(f"Помилка при нарізці відео: {e}")
        return False


def upload_clip_to_azure(
        container_client,
        file_path: str,
        azure_path: str,
        metadata: Dict[str, str]
) -> Dict[str, Any]:
    """
    Завантажує кліп на Azure Blob Storage (заглушка для тестування)
    """
    try:
        # Заглушка - просто логуємо виклик без реального завантаження
        print(f"ЗАГЛУШКА AZURE: Завантаження файлу {file_path}")
        print(f"Цільовий шлях у Azure: {azure_path}")
        print(f"Метадані: {metadata}")

        return {
            "success": True,
            "azure_link": azure_path,
            "metadata": metadata
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def create_cvat_task(
        filename: str,
        file_path: str,
        project_params: Dict[str, Any]
) -> str:
    """
    Створює задачу в CVAT (заглушка для тестування)
    """
    # Заглушка, повертає випадковий ID
    task_id = str(random.randint(10000, 99999))

    # Логуємо дані для дебагу
    print(f"ЗАГЛУШКА CVAT: Створено задачу {task_id} для файлу {filename}")
    print(f"Параметри проєкту: {project_params}")

    return task_id


def get_blob_service_client(account_name: str) -> Any:
    """
    Повертає Azure Blob Service Client (заглушка)
    """
    print(f"ЗАГЛУШКА: Створено Azure Blob Service Client для акаунта {account_name}")
    return object()


def get_blob_container_client(blob_service_client: Any, container_name: str) -> Any:
    """
    Повертає Azure Container Client (заглушка)
    """
    print(f"ЗАГЛУШКА: Створено Azure Container Client для контейнера {container_name}")
    return object()


def get_cvat_task_parameters() -> Dict[str, Dict[str, Any]]:
    """
    Повертає параметри завдань CVAT для різних проєктів
    """
    return {
        "motion-det": {
            "project_id": 22,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        },
        "tracking": {
            "project_id": 17,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        },
        "mil-hardware": {
            "project_id": 10,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        },
        "re-id": {
            "project_id": 17,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        }
    }