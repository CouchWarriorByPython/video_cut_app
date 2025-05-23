import os
import subprocess
import logging
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime
import requests

from azure.storage.blob import BlobServiceClient, ContainerClient

from configs import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Зменшуємо вербальність Azure логів
AZURE_LOGGER = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
AZURE_LOGGER.setLevel(logging.WARNING)


def get_blob_service_client() -> BlobServiceClient:
    """Отримує BlobServiceClient на основі налаштувань"""
    if Settings.azure_connection_string:
        return BlobServiceClient.from_connection_string(Settings.azure_connection_string)
    else:
        raise ValueError("Azure connection string не налаштований")


def get_blob_container_client(blob_service_client: BlobServiceClient) -> ContainerClient:
    """Отримує ContainerClient для налаштованого контейнера"""
    return blob_service_client.get_container_client(container=Settings.azure_storage_container_name)


def download_video_from_azure(url: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """Завантаження відео з URL"""
    if output_dir is None:
        output_dir = Settings.upload_folder

    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Недійсний URL: {url}")

        path_parts = parsed_url.path.strip('/').split('/')
        if path_parts:
            if parsed_url.netloc == 'localhost:8001' and path_parts[-1] == 'video':
                filename = "20250502-1628-IN_Recording.mp4"
            else:
                filename = path_parts[-1]
                if not os.path.splitext(filename)[1]:
                    filename += ".mp4"
        else:
            filename = f"video_{int(datetime.now().timestamp())}.mp4"

        extension = os.path.splitext(filename)[1]

        if os.path.exists(os.path.join(output_dir, filename)):
            base_name, ext = os.path.splitext(filename)
            filename = f"{base_name}_{int(datetime.now().timestamp())}{ext}"

        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)

        response = requests.get(url, stream=True, timeout=30)

        if response.status_code != 200:
            raise ValueError(f"Помилка отримання відео. Статус: {response.status_code}")

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        web_path = f"/videos/{filename}"

        return {
            "success": True,
            "azure_link": url,
            "filename": filename,
            "extension": extension[1:] if extension.startswith('.') else extension,
            "local_path": web_path,
            "file_path": file_path
        }
    except Exception as e:
        logger.error(f"Помилка завантаження відео: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def get_command_auth_str() -> str:
    """Формує auth string для CVAT CLI команд"""
    if not Settings.validate_cvat_config():
        raise ValueError("CVAT налаштування не знайдені")

    return f"cvat-cli --auth {Settings.cvat_username}:{Settings.cvat_password} --server-host {Settings.cvat_host} --server-port {Settings.cvat_port}"


def execute_cvat_command(cli_command: str) -> subprocess.CompletedProcess:
    """Виконує CVAT CLI команду"""
    auth_str = get_command_auth_str()
    command = f"{auth_str} {cli_command}"
    logger.info(f"Виконання команди: {command}")
    return subprocess.run(command, shell=True, capture_output=True)


def get_default_cvat_project_params(project_name: str) -> Dict[str, Any]:
    """Отримання дефолтних CVAT параметрів проєкту"""
    default_projects = {
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

    return default_projects.get(project_name, {
        "project_id": 1,
        "overlap": 5,
        "segment_size": 400,
        "image_quality": 100
    })


def get_cvat_task_parameters() -> Dict[str, Dict[str, Any]]:
    """Отримання всіх CVAT параметрів"""
    return {
        "motion-det": get_default_cvat_project_params("motion-det"),
        "tracking": get_default_cvat_project_params("tracking"),
        "mil-hardware": get_default_cvat_project_params("mil-hardware"),
        "re-id": get_default_cvat_project_params("re-id")
    }


def trim_video_clip(
        source_path: str,
        output_path: str,
        start_time: str,
        end_time: str
) -> bool:
    """Нарізає відео фрагмент за допомогою FFmpeg"""
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
            "-loglevel", Settings.ffmpeg_log_level,
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
    """Завантажує кліп на Azure Blob Storage"""
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
        project_params: Dict[str, Any]
) -> Optional[str]:
    """Створює задачу в CVAT через CLI"""
    try:
        project_id = project_params.get("project_id")
        overlap = project_params.get("overlap", 5)
        segment_size = project_params.get("segment_size", 400)
        image_quality = project_params.get("image_quality", 100)

        if not project_id:
            logger.error("project_id не вказано в параметрах")
            return None

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

        result = execute_cvat_command(cli_command)

        if result.returncode == 0:
            output = result.stdout.decode("utf-8")
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