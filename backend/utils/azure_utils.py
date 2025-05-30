import os
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ResourceNotFoundError

from backend.config.settings import Settings
from backend.utils.logger import get_logger

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


def download_blob_to_local(azure_url: str, local_path: str) -> Dict[str, Any]:
    """Завантажує blob з Azure у локальний файл"""
    try:
        blob_info = parse_azure_blob_url(azure_url)
        blob_service_client = get_blob_service_client()

        blob_client = blob_service_client.get_blob_client(
            container=blob_info["container_name"],
            blob=blob_info["blob_name"]
        )

        if not blob_client.exists():
            raise ResourceNotFoundError(f"Blob не знайдено: {azure_url}")

        # Створюємо директорію якщо не існує
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        logger.debug(f"Завантаження blob {azure_url} в {local_path}")

        with open(local_path, "wb") as download_file:
            blob_data = blob_client.download_blob()
            download_file.write(blob_data.readall())

        return {
            "success": True,
            "local_path": local_path,
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
        logger.debug(f"Завантаження файлу {file_path} на Azure в {azure_path}")

        with open(file_path, "rb") as data:
            container_client.upload_blob(
                name=azure_path,
                data=data,
                overwrite=True,
                metadata=metadata
            )

        logger.debug(f"Файл успішно завантажено на Azure: {azure_path}")

        return {
            "success": True,
            "azure_path": azure_path,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Помилка завантаження на Azure: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }