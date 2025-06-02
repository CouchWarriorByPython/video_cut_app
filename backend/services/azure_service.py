import os
from typing import Dict, Any

from azure.storage.blob import BlobServiceClient, ContainerClient

from backend.utils.azure_utils import (
    get_blob_service_client, get_blob_container_client,
    parse_azure_blob_url, download_blob_to_local, upload_clip_to_azure
)
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class AzureService:
    """Сервіс для роботи з Azure Storage"""

    def __init__(self):
        self._blob_service_client = None
        self._container_client = None

    @property
    def blob_service_client(self) -> BlobServiceClient:
        """Lazy ініціалізація BlobServiceClient"""
        if self._blob_service_client is None:
            self._blob_service_client = get_blob_service_client()
        return self._blob_service_client

    @property
    def container_client(self) -> ContainerClient:
        """Lazy ініціалізація ContainerClient"""
        if self._container_client is None:
            self._container_client = get_blob_container_client(self.blob_service_client)
        return self._container_client

    def validate_azure_url(self, url: str) -> Dict[str, Any]:
        """Валідує Azure blob URL та перевіряє доступність"""
        try:
            blob_info = parse_azure_blob_url(url)

            if blob_info["account_name"] != Settings.azure_storage_account_name:
                return {
                    "valid": False,
                    "error": f"URL повинен бути з storage account '{Settings.azure_storage_account_name}'"
                }

            blob_client = self.blob_service_client.get_blob_client(
                container=blob_info["container_name"],
                blob=blob_info["blob_name"]
            )

            if not blob_client.exists():
                return {
                    "valid": False,
                    "error": "Файл не знайдено в Azure Storage"
                }

            properties = blob_client.get_blob_properties()
            filename = os.path.basename(blob_info["blob_name"])

            return {
                "valid": True,
                "filename": filename,
                "blob_info": blob_info
            }

        except Exception as e:
            logger.error(f"Помилка валідації Azure URL {url}: {str(e)}")
            return {
                "valid": False,
                "error": f"Помилка валідації URL: {str(e)}"
            }

    def download_video_to_local(self, azure_url: str, local_path: str) -> Dict[str, Any]:
        """Завантажує відео з Azure Storage локально"""
        try:
            # Створюємо директорію якщо не існує
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            result = download_blob_to_local(azure_url, local_path)

            if result["success"]:
                logger.info(f"Відео завантажено локально: {local_path}")
            else:
                logger.error(f"Помилка завантаження відео: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Помилка при завантаженні відео {azure_url}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def upload_clip(self, file_path: str, azure_path: str, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Завантажує кліп на Azure Storage"""
        try:
            result = upload_clip_to_azure(
                container_client=self.container_client,
                file_path=file_path,
                azure_path=azure_path,
                metadata=metadata
            )

            if result["success"]:
                # Формуємо повний Azure URL
                full_azure_url = f"{Settings.get_azure_account_url()}/{Settings.azure_storage_container_name}/{azure_path}"
                result["azure_url"] = full_azure_url

            return result

        except Exception as e:
            logger.error(f"Помилка при завантаженні кліпу на Azure: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }