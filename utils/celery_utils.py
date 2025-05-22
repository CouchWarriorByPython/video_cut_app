import os
import subprocess
from typing import Dict, Any
import random

AZURE_STORAGE_ACCOUNT_NAME = "test_acc"
AZURE_STORAGE_CONTAINER_NAME = "test_container"
AZURE_OUTPUT_PREFIX = "clips"


def format_filename(
        metadata: Dict[str, Any],
        original_filename: str,
        clip_id: int,
        where: str = "",
        when: str = ""
) -> str:
    """
    Форматує ім'я файлу на основі метаданих та атрибутів відео
    """
    video_base_name = os.path.splitext(os.path.basename(original_filename))[0]

    uav_type = metadata.get("uav_type", "unknown")

    filename_parts = [uav_type]

    if where:
        filename_parts.append(where)
    if when:
        filename_parts.append(when)

    filename_parts.append(f"{video_base_name}_cut{clip_id}")

    return "_".join(filename_parts)


def trim_video_clip(
        source_path: str,
        output_path: str,
        start_time: str,
        end_time: str
) -> bool:
    """
    Нарізає відео фрагмент

    Args:
        source_path: Шлях до вихідного відео
        output_path: Шлях для збереження кліпу
        start_time: Час початку у форматі HH:MM:SS
        end_time: Час кінця у форматі HH:MM:SS

    Returns:
        bool: True якщо успішно, False якщо помилка
    """
    try:
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

        result = subprocess.run(command, capture_output=True, text=True)

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

    Args:
        container_client: Azure контейнер клієнт
        file_path: Локальний шлях до файлу
        azure_path: Шлях у Azure
        metadata: Метадані файлу

    Returns:
        Dict[str, Any]: Результат завантаження
    """
    try:
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

    Args:
        filename: Назва файлу
        file_path: Шлях до файлу
        project_params: Параметри проєкту CVAT

    Returns:
        str: ID створеної задачі
    """
    task_id = str(random.randint(10000, 99999))

    print(f"ЗАГЛУШКА CVAT: Створено задачу {task_id} для файлу {filename}")
    print(f"Параметри проєкту: {project_params}")

    return task_id


def get_blob_service_client(account_name: str) -> Any:
    """
    Повертає Azure Blob Service Client (заглушка)

    Args:
        account_name: Назва Azure Storage Account

    Returns:
        Any: Mock об'єкт клієнта
    """
    print(f"ЗАГЛУШКА: Створено Azure Blob Service Client для акаунта {account_name}")
    return object()


def get_blob_container_client(blob_service_client: Any, container_name: str) -> Any:
    """
    Повертає Azure Container Client (заглушка)

    Args:
        blob_service_client: Azure Blob Service Client
        container_name: Назва контейнера

    Returns:
        Any: Mock об'єкт контейнера
    """
    print(f"ЗАГЛУШКА: Створено Azure Container Client для контейнера {container_name}")
    return object()


def get_cvat_task_parameters() -> Dict[str, Dict[str, Any]]:
    """
    Повертає параметри завдань CVAT для різних проєктів

    Returns:
        Dict[str, Dict[str, Any]]: Параметри для кожного типу проєкту
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