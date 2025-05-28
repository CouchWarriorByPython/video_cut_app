import os
import subprocess
import logging
import re
import tempfile
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime

from azure.storage.blob import BlobServiceClient, ContainerClient, BlobClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ResourceNotFoundError

from configs import Settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Зменшуємо вербальність Azure логів
AZURE_LOGGER = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
AZURE_LOGGER.setLevel(logging.WARNING)


def get_blob_service_client() -> BlobServiceClient:
    """Отримує BlobServiceClient на основі service principal credentials"""
    try:
        credential = ClientSecretCredential(
            tenant_id=Settings.azure_tenant_id,
            client_id=Settings.azure_client_id,
            client_secret=Settings.azure_client_secret
        )

        return BlobServiceClient(
            account_url=Settings.get_azure_account_url(),
            credential=credential
        )
    except Exception as e:
        logger.error(f"Помилка створення BlobServiceClient: {str(e)}")
        raise


def get_blob_container_client(blob_service_client: BlobServiceClient) -> ContainerClient:
    """Отримує ContainerClient для налаштованого контейнера"""
    return blob_service_client.get_container_client(container=Settings.azure_storage_container_name)


def parse_azure_blob_url(azure_url: str) -> Dict[str, str]:
    """Парсить Azure blob URL та повертає компоненти"""
    try:
        parsed = urlparse(azure_url)
        path_parts = parsed.path.strip('/').split('/', 2)

        if len(path_parts) < 2:
            raise ValueError("Некоректний Azure blob URL")

        container_name = path_parts[0]
        blob_name = '/'.join(path_parts[1:]) if len(path_parts) > 1 else path_parts[1]

        return {
            "account_name": parsed.netloc.split('.')[0],
            "container_name": container_name,
            "blob_name": blob_name
        }
    except Exception as e:
        logger.error(f"Помилка парсингу Azure URL {azure_url}: {str(e)}")
        raise


def download_blob_to_temp(azure_url: str) -> Dict[str, Any]:
    """Завантажує blob з Azure в тимчасовий файл"""
    try:
        blob_info = parse_azure_blob_url(azure_url)
        blob_service_client = get_blob_service_client()

        blob_client = blob_service_client.get_blob_client(
            container=blob_info["container_name"],
            blob=blob_info["blob_name"]
        )

        # Перевіряємо існування blob
        if not blob_client.exists():
            raise ResourceNotFoundError(f"Blob не знайдено: {azure_url}")

        # Отримуємо властивості blob
        blob_properties = blob_client.get_blob_properties()
        filename = os.path.basename(blob_info["blob_name"])

        # Створюємо тимчасовий файл
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(filename)[1],
            dir=Settings.temp_folder
        )

        logger.info(f"Завантаження blob {azure_url} в {temp_file.name}")

        # Завантажуємо blob
        with open(temp_file.name, "wb") as download_file:
            blob_data = blob_client.download_blob()
            download_file.write(blob_data.readall())

        return {
            "success": True,
            "local_path": temp_file.name,
            "filename": filename,
            "size": blob_properties.size,
            "content_type": blob_properties.content_settings.content_type or "video/mp4"
        }

    except Exception as e:
        logger.error(f"Помилка завантаження blob {azure_url}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def upload_clip_to_azure(
        container_client: ContainerClient,
        file_path: str,
        azure_path: str,
        metadata: Dict[str, str]
) -> Dict[str, Any]:
    """Завантажує кліп на Azure Blob Storage"""
    try:
        logger.info(f"Завантаження файлу {file_path} на Azure в {azure_path}")

        with open(file_path, "rb") as data:
            blob_client = container_client.upload_blob(
                name=azure_path,
                data=data,
                overwrite=True,
                metadata=metadata
            )

        logger.info(f"Файл успішно завантажено на Azure: {azure_path}")

        return {
            "success": True,
            "azure_path": azure_path,
            "blob_url": f"{Settings.get_azure_account_url()}/{Settings.azure_storage_container_name}/{azure_path}",
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Помилка завантаження на Azure: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def get_command_auth_str() -> str:
    """Формує auth string для CVAT CLI команд"""
    return f"cvat-cli --auth {Settings.cvat_username}:{Settings.cvat_password} --server-host {Settings.cvat_host} --server-port {Settings.cvat_port}"


def execute_cvat_command(cli_command: str) -> subprocess.CompletedProcess:
    """Виконує CVAT CLI команду"""
    auth_str = get_command_auth_str()
    command = f"{auth_str} {cli_command}"
    logger.info(f"Виконання команди: {command}")
    return subprocess.run(command, shell=True, capture_output=True)


def get_default_cvat_project_params(project_name: str) -> Dict[str, Any]:
    """Отримує дефолтні CVAT параметри проєкту"""
    default_projects = {
        "motion-det": {
            "project_id": 5,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        },
        "tracking": {
            "project_id": 6,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        },
        "mil-hardware": {
            "project_id": 7,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        },
        "re-id": {
            "project_id": 8,
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


def format_filename(
        metadata: Dict[str, Any],
        original_filename: str,
        project: str,
        clip_id: int,
        where: str = "",
        when: str = ""
) -> str:
    """Форматує ім'я файлу на основі метаданих та атрибутів відео"""
    video_base_name = os.path.splitext(os.path.basename(original_filename))[0]
    uav_type = metadata.get("uav_type", "unknown")

    filename_parts = [uav_type]

    if where:
        filename_parts.append(where)
    if when:
        filename_parts.append(when)

    filename_parts.append(f"{video_base_name}_{project}_{clip_id}")

    return "_".join(filename_parts) + ".mp4"


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


def cleanup_temp_file(file_path: str) -> None:
    """Видаляє тимчасовий файл"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Видалено тимчасовий файл: {file_path}")
    except Exception as e:
        logger.error(f"Помилка видалення тимчасового файлу {file_path}: {str(e)}")