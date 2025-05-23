import os
import subprocess
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime
import requests

from azure.storage.blob import BlobServiceClient, ContainerClient

import config
from config import logger

# Azure configuration
AZURE_STORAGE_ACCOUNT_NAME = "test_acc"
AZURE_STORAGE_CONTAINER_NAME = "test_container"
AZURE_OUTPUT_PREFIX = "clips"

# Reduce Azure HTTP logging
AZURE_LOGGER = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
AZURE_LOGGER.setLevel(logging.WARNING)


def __get_connection_str(credentials_config: dict) -> str:
    """
    Azure configuration dictionary that is read from configs/general.yaml file, "azure" section.
    """
    url = credentials_config["url_pattern"]
    url_variables = dict()
    for variable in credentials_config["url_pattern_variables"]:
        if variable["type"] == "string":
            url_variables[variable["name"]] = variable["value"]
        elif variable["type"] == "environment_variable_name":
            url_variables[variable["name"]] = os.getenv(variable["value"])
    return url.format(**url_variables)


def get_blob_service_client(resource_name: str) -> BlobServiceClient:
    """
    Отримує BlobServiceClient для вказаного ресурсу Azure
    """
    conf = config.AZURE_CONFIG
    client = None

    for resource in conf['resources']:
        if resource["resource_name"] == resource_name:
            if resource["resource_type"] == 'storage_account':
                client = BlobServiceClient.from_connection_string(
                    conn_str=__get_connection_str(credentials_config=resource["credentials"])
                )
            elif resource["resource_type"] == 'blob_container_sas':
                client = BlobServiceClient(
                    account_url=__get_connection_str(credentials_config=resource["credentials"])
                )

    if client is None:
        raise ValueError('No such resource_name in the config.')

    return client


def get_blob_container_client(blob_service_client: BlobServiceClient, container_name: str) -> ContainerClient:
    """
    Отримує ContainerClient для вказаного контейнера
    """
    return blob_service_client.get_container_client(container=container_name)


def download_video_from_azure(url: str, output_dir: str = "source_videos") -> Dict[str, Any]:
    """
    Завантаження відео з URL
    """
    try:
        # Перевіряємо, чи URL дійсний
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Недійсний URL: {url}")

        # Отримання імені файлу з URL шляху
        path_parts = parsed_url.path.strip('/').split('/')
        if path_parts:
            # Перевірка на мок-сервер
            if parsed_url.netloc == 'localhost:8001' and path_parts[-1] == 'video':
                filename = "20250502-1628-IN_Recording.mp4"
            else:
                # Обробка для інших URL
                filename = path_parts[-1]
                # Додаємо розширення, якщо відсутнє
                if not os.path.splitext(filename)[1]:
                    filename += ".mp4"
        else:
            # Якщо не можемо отримати ім'я з URL, створюємо його
            filename = f"video_{int(datetime.utcnow().timestamp())}.mp4"

        # Отримуємо розширення
        extension = os.path.splitext(filename)[1]

        # Перевіряємо чи файл вже існує
        if os.path.exists(os.path.join(output_dir, filename)):
            # Додаємо timestamp до імені, щоб уникнути перезапису
            base_name, ext = os.path.splitext(filename)
            filename = f"{base_name}_{int(datetime.utcnow().timestamp())}{ext}"

        # Створюємо директорію, якщо її не існує
        os.makedirs(output_dir, exist_ok=True)

        # Шлях для збереження файлу
        file_path = os.path.join(output_dir, filename)

        # Завантажуємо файл
        response = requests.get(url, stream=True, timeout=30)

        # Перевірка успішності запиту
        if response.status_code != 200:
            raise ValueError(f"Помилка отримання відео. Статус: {response.status_code}")

        # Записуємо файл блоками для економії пам'яті
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # фільтр порожніх частин
                    f.write(chunk)

        # Повертаємо URL для веб-доступу, а не повний системний шлях
        web_path = f"/videos/{filename}"

        return {
            "success": True,
            "azure_link": url,
            "filename": filename,
            "extension": extension[1:] if extension.startswith('.') else extension,
            "local_path": web_path,
            "file_path": file_path  # Системний шлях для інших операцій якщо потрібно
        }
    except Exception as e:
        import traceback
        print(f"Помилка завантаження відео: {str(e)}")
        print(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }


def get_command_auth_str(remote_name: str) -> str:
    """
    Формує auth string для CVAT CLI команд
    """
    remote_config = config.general_config["remote"][remote_name]
    host = remote_config["host"]
    port = remote_config["port"]
    user = remote_config["cvat_ui_user_var_name"]
    password = remote_config["cvat_ui_pass_var_name"]
    cvat_username = os.getenv(user)
    cvat_password = os.getenv(password)
    return f"cvat-cli --auth {cvat_username}:{cvat_password} --server-host {host} --server-port {port}"


def execute_cvat_command(remote_name: str, cli_command: str) -> subprocess.CompletedProcess:
    """
    Виконує CVAT CLI команду
    """
    auth_str = get_command_auth_str(remote_name=remote_name)
    command = f"{auth_str} {cli_command}"
    logger.info(f"Command: {command}")
    return subprocess.run(command, shell=True, capture_output=True)


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
    Нарізає відео фрагмент за допомогою FFmpeg
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
        logger.info(f"Запуск команди: {command_str}")

        result = subprocess.run(command, capture_output=True, text=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Кліп успішно створено: {output_path}")
            return True
        else:
            logger.error(f"Помилка при створенні кліпу: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Помилка при нарізці відео: {e}")
        return False


def upload_clip_to_azure(
        container_client: ContainerClient,
        file_path: str,
        azure_path: str,
        metadata: Dict[str, str]
) -> Dict[str, Any]:
    """
    Завантажує кліп на Azure Blob Storage
    """
    try:
        logger.info(f"Завантаження файлу {file_path} на Azure")

        with open(file_path, "rb") as data:
            blob_client = container_client.upload_blob(
                name=azure_path,
                data=data,
                overwrite=True,
                metadata=metadata,
                logger=AZURE_LOGGER
            )

        logger.info(f"Файл успішно завантажено на Azure: {azure_path}")

        return {
            "success": True,
            "azure_link": azure_path,
            "blob_client": blob_client,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Помилка завантаження на Azure: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def create_cvat_task(
        filename: str,
        file_path: str,
        project_params: Dict[str, Any],
        remote_name: str = "default"
) -> Optional[str]:
    """
    Створює задачу в CVAT через CLI
    """
    try:
        # Формуємо параметри для CVAT CLI
        project_id = project_params.get("project_id")
        overlap = project_params.get("overlap", 5)
        segment_size = project_params.get("segment_size", 400)
        image_quality = project_params.get("image_quality", 100)

        if not project_id:
            logger.error("project_id не вказано в параметрах")
            return None

        # Формуємо команду створення задачі
        cli_command = (
            f"create {filename} "
            f"local {file_path} "
            f"--project_id {project_id} "
            f"--overlap {overlap} "
            f"--segment_size {segment_size} "
            f"--image_quality {image_quality} "
            "--use_cache --use_zip_chunks"
        )

        logger.info(f"Створення CVAT задачі для {filename}")

        result = execute_cvat_command(remote_name=remote_name, cli_command=cli_command)

        if result.returncode == 0:
            # Витягуємо task ID з виводу
            output = result.stdout.decode("utf-8")
            import re
            match = re.search(r"Created task ID: (\d+)", output)
            task_id = match.group(1) if match else None

            if task_id:
                logger.info(f"CVAT задача створена успішно: {task_id}")
                return task_id
            else:
                logger.warning(f"Не вдалося витягти task ID з виводу: {output}")
                return None
        else:
            error_output = result.stderr.decode("utf-8")
            logger.error(f"Помилка створення CVAT задачі: {error_output}")
            return None

    except Exception as e:
        logger.error(f"Помилка при створенні CVAT задачі для {filename}: {str(e)}")
        return None


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