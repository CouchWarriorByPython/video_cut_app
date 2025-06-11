import os
import logging
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Callable, Optional
from urllib.parse import urlparse

from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ResourceNotFoundError

from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "utils.log")

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
    """Парсить Azure blob URL та повертає компоненти з підтримкою українських символів"""
    try:
        # Декодуємо URL для правильного парсингу українських символів
        decoded_url = urllib.parse.unquote(azure_url)
        parsed = urlparse(decoded_url)
        path_parts = parsed.path.strip('/').split('/', 2)

        if len(path_parts) < 2:
            raise ValueError("Некоректний Azure blob URL")

        container_name = path_parts[0]
        blob_name = '/'.join(path_parts[1:]) if len(path_parts) > 1 else path_parts[1]

        return {
            "account_name": parsed.netloc.split('.')[0],
            "container_name": container_name,
            "blob_name": blob_name,
            "original_url": azure_url
        }
    except Exception as e:
        logger.error(f"Помилка парсингу Azure URL {azure_url}: {str(e)}")
        raise


def download_chunk(blob_client, start: int, end: int, chunk_index: int) -> bytes:
    """Завантажує частину blob"""
    try:
        logger.debug(f"Завантаження частини {chunk_index}: {start}-{end} ({(end - start + 1) / (1024 * 1024):.1f} MB)")
        stream = blob_client.download_blob(offset=start, length=end - start + 1)
        return stream.readall()
    except Exception as e:
        logger.error(f"Помилка завантаження частини {chunk_index}: {str(e)}")
        raise


def download_blob_to_local_parallel_with_progress(
        azure_url: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    """Завантажує blob з Azure у локальний файл з паралельним завантаженням та прогрес-трекінгом"""
    try:
        blob_info = parse_azure_blob_url(azure_url)
        blob_service_client = get_blob_service_client()

        blob_client = blob_service_client.get_blob_client(
            container=blob_info["container_name"],
            blob=blob_info["blob_name"]
        )

        if not blob_client.exists():
            raise ResourceNotFoundError(f"Blob не знайдено: {azure_url}")

        # Отримуємо розмір файлу
        properties = blob_client.get_blob_properties()
        file_size = properties.size

        logger.info(f"Паралельне завантаження blob {azure_url} ({file_size / (1024 * 1024):.1f} MB) в {local_path}")

        # Створюємо директорію якщо не існує
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Якщо файл невеликий, завантажуємо звичайним способом з прогресом
        if file_size < Settings.azure_download_chunk_size * 2:
            return download_blob_to_local_simple_with_progress(blob_client, local_path, file_size, progress_callback)

        # Розбиваємо на частини
        chunks = []
        for i in range(0, file_size, Settings.azure_download_chunk_size):
            start = i
            end = min(i + Settings.azure_download_chunk_size - 1, file_size - 1)
            chunks.append((start, end, len(chunks)))

        logger.info(
            f"Завантаження {len(chunks)} частин по {Settings.azure_download_chunk_size / (1024 * 1024):.1f} MB з {Settings.azure_max_concurrency} потоками")

        # Змінна для відстеження завантажених байтів
        downloaded_bytes = 0
        bytes_lock = threading.Lock()

        def download_chunk_with_progress(blob_client, start: int, end: int, chunk_index: int) -> bytes:
            """Завантажує частину blob з відстеженням прогресу"""
            nonlocal downloaded_bytes
            try:
                logger.debug(
                    f"Завантаження частини {chunk_index}: {start}-{end} ({(end - start + 1) / (1024 * 1024):.1f} MB)")
                stream = blob_client.download_blob(offset=start, length=end - start + 1)
                chunk_data = stream.readall()

                # Оновлюємо прогрес thread-safe
                with bytes_lock:
                    downloaded_bytes += len(chunk_data)
                    if progress_callback:
                        progress_callback(downloaded_bytes, file_size)

                return chunk_data
            except Exception as e:
                logger.error(f"Помилка завантаження частини {chunk_index}: {str(e)}")
                raise

        # Паралельне завантаження частин
        with ThreadPoolExecutor(max_workers=Settings.azure_max_concurrency) as executor:
            futures = []

            for start, end, chunk_index in chunks:
                future = executor.submit(download_chunk_with_progress, blob_client, start, end, chunk_index)
                futures.append((chunk_index, future))

            # Збираємо результати в правильному порядку
            chunk_results = {}
            for chunk_index, future in futures:
                chunk_results[chunk_index] = future.result()

        # Записуємо файл
        with open(local_path, "wb") as output_file:
            for i in range(len(chunks)):
                output_file.write(chunk_results[i])

        logger.info(f"Паралельне завантаження завершено: {local_path}")

        return {
            "success": True,
            "local_path": local_path,
            "file_size": file_size
        }

    except Exception as e:
        logger.error(f"Помилка паралельного завантаження blob {azure_url}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def download_blob_to_local_simple_with_progress(
        blob_client,
        local_path: str,
        file_size: int,
        progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    """Простий спосіб завантаження для невеликих файлів з прогрес-трекінгом"""
    try:
        logger.debug(f"Звичайне завантаження blob в {local_path}")

        downloaded_bytes = 0
        with open(local_path, "wb") as download_file:
            blob_data = blob_client.download_blob()
            # Використовуємо буферизоване читання з прогресом
            for chunk in blob_data.chunks():
                download_file.write(chunk)
                downloaded_bytes += len(chunk)

                if progress_callback:
                    progress_callback(downloaded_bytes, file_size)

        return {
            "success": True,
            "local_path": local_path,
            "file_size": file_size
        }
    except Exception as e:
        logger.error(f"Помилка завантаження blob: {str(e)}")
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