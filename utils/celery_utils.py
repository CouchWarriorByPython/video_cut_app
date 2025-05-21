import os
import subprocess
import re
import tempfile
import shlex
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Any, Optional
import random

# Конфігурація Azure
AZURE_STORAGE_ACCOUNT_NAME = "test_acc"
AZURE_STORAGE_CONTAINER_NAME = "test_container"
AZURE_OUTPUT_PREFIX = "clips"


def format_filename(metadata: Dict[str, Any], original_filename: str, project: str, clip_id: int) -> str:
    """
    Форматує ім'я файлу на основі метаданих
    """
    uav_type = metadata.get("uav_type", "unknown")
    where = metadata.get("where", "unknown")
    when = metadata.get("when", datetime.now().strftime("%Y%m%d"))

    base_name = os.path.splitext(original_filename)[0]
    return f"{project}_{uav_type}_{where}_{when}_{base_name}_cut{clip_id}"


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
            output_path,
        ]
        command_str = " ".join(command)
        print(f"Запуск команди: {command_str}")

        # Виконуємо команду ffmpeg
        subprocess.run(command, check=True)

        # Перевіряємо, чи файл був створений
        return os.path.exists(output_path)
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
            "azure_path": azure_path,
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
    return object()  # Повертаємо простий об'єкт для тестування


def get_blob_container_client(blob_service_client: Any, container_name: str) -> Any:
    """
    Повертає Azure Container Client (заглушка)
    """
    print(f"ЗАГЛУШКА: Створено Azure Container Client для контейнера {container_name}")
    return object()  # Повертаємо простий об'єкт для тестування


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