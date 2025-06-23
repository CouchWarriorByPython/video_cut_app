import os
from typing import Dict, Any, List

from azure.storage.blob import BlobServiceClient, ContainerClient

from backend.utils.azure_utils import (
    get_blob_service_client, get_blob_container_client,
    download_blob_to_local_parallel_with_progress, upload_clip_to_azure, parse_azure_blob_url
)

from backend.models.database import AzureFilePath
from backend.utils.azure_path_utils import (
    parse_azure_blob_url_to_path, azure_path_to_url,
    extract_filename_from_azure_path, validate_azure_path_structure
)

from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class AzureService:
    """Service for working with Azure Storage with new path structure"""

    def __init__(self):
        self._blob_service_client = None
        self._container_client = None

    @property
    def blob_service_client(self) -> BlobServiceClient:
        """Lazy initialization of BlobServiceClient"""
        if self._blob_service_client is None:
            self._blob_service_client = get_blob_service_client()
        return self._blob_service_client

    @property
    def container_client(self) -> ContainerClient:
        """Lazy initialization of ContainerClient"""
        if self._container_client is None:
            self._container_client = get_blob_container_client(self.blob_service_client)
        return self._container_client

    def validate_azure_url(self, url: str) -> Dict[str, Any]:
        """Validate Azure blob URL and return AzureFilePath structure"""
        try:
            azure_path = parse_azure_blob_url_to_path(url)

            if azure_path.account_name != Settings.azure_storage_account_name:
                return {
                    "valid": False,
                    "error": f"URL must be from storage account '{Settings.azure_storage_account_name}'"
                }

            if not validate_azure_path_structure(azure_path):
                return {
                    "valid": False,
                    "error": "Invalid Azure path structure"
                }

            blob_client = self.blob_service_client.get_blob_client(
                container=azure_path.container_name,
                blob=azure_path.blob_path
            )

            if not blob_client.exists():
                logger.error(f"Blob does not exist: {azure_path.blob_path}")
                return {
                    "valid": False,
                    "error": "File not found in Azure Storage"
                }

            properties = blob_client.get_blob_properties()
            filename = extract_filename_from_azure_path(azure_path)

            logger.info(f"Blob found: {filename}, size: {properties.size} bytes")

            return {
                "valid": True,
                "filename": filename,
                "azure_path": azure_path,
                "size_bytes": properties.size
            }

        except Exception as e:
            logger.error(f"Error validating Azure URL {url}: {str(e)}")
            return {
                "valid": False,
                "error": f"URL validation error: {str(e)}"
            }

    def download_video_to_local_with_progress(
            self,
            azure_path: AzureFilePath,
            local_path: str,
            progress_callback=None
    ) -> Dict[str, Any]:
        """Download video from Azure Storage locally with progress"""
        try:
            azure_url = azure_path_to_url(azure_path)
            return download_blob_to_local_parallel_with_progress(
                azure_url, local_path, progress_callback
            )

        except Exception as e:
            logger.error(f"Error downloading video {azure_path.blob_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def upload_clip(self, file_path: str, azure_path: AzureFilePath, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Upload clip to Azure Storage"""
        try:
            result = upload_clip_to_azure(
                container_client=self.container_client,
                file_path=file_path,
                azure_path=azure_path.blob_path,
                metadata=metadata
            )

            if result["success"]:
                result["azure_path"] = azure_path
                result["azure_url"] = azure_path_to_url(azure_path)

            return result

        except Exception as e:
            logger.error(f"Error uploading clip to Azure: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_file_info(self, azure_path: AzureFilePath) -> Dict[str, Any]:
        """Get file information from Azure Storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=azure_path.container_name,
                blob=azure_path.blob_path
            )

            if not blob_client.exists():
                return {
                    "success": False,
                    "error": "File not found"
                }

            properties = blob_client.get_blob_properties()

            return {
                "success": True,
                "size_bytes": properties.size,
                "size_MB": properties.size / (1024 * 1024),
                "last_modified": properties.last_modified,
                "content_type": properties.content_settings.content_type,
                "filename": extract_filename_from_azure_path(azure_path)
            }

        except Exception as e:
            logger.error(f"Error getting file info for {azure_path.blob_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def delete_file(self, azure_path: AzureFilePath) -> Dict[str, Any]:
        """Delete file from Azure Storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=azure_path.container_name,
                blob=azure_path.blob_path
            )

            blob_client.delete_blob()

            logger.info(f"File deleted from Azure: {azure_path.blob_path}")

            return {
                "success": True,
                "message": "File deleted successfully"
            }

        except Exception as e:
            logger.error(f"Error deleting file {azure_path.blob_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def list_videos_in_folder(self, folder_url: str) -> List[Dict[str, Any]]:
        """Отримує список відео файлів у вказаній папці Azure"""
        try:
            parsed = parse_azure_blob_url(folder_url)
            prefix = parsed["blob_name"]

            # Додаємо слеш якщо його немає
            if not prefix.endswith('/'):
                prefix += '/'

            container_client = self.blob_service_client.get_container_client(
                parsed["container_name"]
            )

            video_extensions = {'.mp4', '.avi', '.mov', '.mkv'}
            videos = []

            # Отримуємо всі блоби з префіксом
            blobs = container_client.list_blobs(name_starts_with=prefix)

            for blob in blobs:
                # Перевіряємо що це файл, а не папка
                if not blob.name.endswith('/'):
                    # Перевіряємо що це відео
                    file_ext = os.path.splitext(blob.name)[1].lower()
                    if file_ext in video_extensions:
                        # Перевіряємо що файл на тому ж рівні (не в підпапці)
                        relative_path = blob.name[len(prefix):]
                        if '/' not in relative_path:
                            full_url = f"https://{parsed['account_name']}.blob.core.windows.net/{parsed['container_name']}/{blob.name}"
                            videos.append({
                                "url": full_url,
                                "filename": os.path.basename(blob.name),
                                "size_bytes": blob.size
                            })

            logger.info(f"Знайдено {len(videos)} відео файлів у папці {prefix}")
            return videos

        except Exception as e:
            logger.error(f"Помилка отримання списку відео з папки {folder_url}: {str(e)}")
            return []