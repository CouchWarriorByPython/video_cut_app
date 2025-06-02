import os
from typing import Dict, Any, Optional
from datetime import datetime

from backend.database.repositories.source_video import SyncSourceVideoRepository
from backend.services.azure_service import AzureService
from backend.utils.video_utils import get_local_video_path
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class VideoService:
    """Сервіс для роботи з відео"""

    def __init__(self):
        self.source_repo = SyncSourceVideoRepository()
        self.azure_service = AzureService()

    def validate_and_register_video(self, video_url: str, where: Optional[str], when: Optional[str]) -> Dict[str, Any]:
        """Валідує, завантажує та реєструє відео"""
        try:
            # Валідація Azure URL
            validation_result = self.azure_service.validate_azure_url(video_url)

            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Невірний Azure URL: {validation_result['error']}"
                }

            filename = validation_result["filename"]
            local_path = get_local_video_path(filename)

            # Завантаження відео локально
            download_result = self.azure_service.download_video_to_local(video_url, local_path)

            if not download_result["success"]:
                return {
                    "success": False,
                    "error": f"Помилка завантаження відео: {download_result['error']}"
                }

            # Збереження в БД
            video_record = {
                "azure_link": video_url,
                "filename": filename,
                "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "when": when,
                "where": where,
                "status": "not_annotated"
            }

            self.source_repo.create_indexes()
            record_id = self.source_repo.save_annotation(video_record)

            logger.info(f"Відео завантажено та зареєстровано: {filename}")

            return {
                "success": True,
                "_id": record_id,
                "azure_link": video_url,
                "filename": filename,
                "message": "Відео успішно зареєстровано та завантажено локально"
            }

        except Exception as e:
            logger.error(f"Помилка при реєстрації відео: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_video_for_streaming(self, azure_link: str) -> Optional[str]:
        """Отримує локальний шлях до відео для стрімінгу"""
        try:
            annotation = self.source_repo.get_annotation(azure_link)

            if not annotation:
                logger.error(f"Відео не знайдено: {azure_link}")
                return None

            filename = annotation.get("filename")
            if not filename:
                logger.error(f"Назва файлу не знайдена для: {azure_link}")
                return None

            local_path = get_local_video_path(filename)

            if not os.path.exists(local_path):
                logger.error(f"Локальний файл не знайдено: {local_path}")
                return None

            return local_path

        except Exception as e:
            logger.error(f"Помилка при отриманні відео для стрімінгу: {str(e)}")
            return None

    def get_videos_list(self) -> Dict[str, Any]:
        """Отримує список відео які ще не анотовані"""
        try:
            videos_data = self.source_repo.get_all_annotations(filter_query={"status": {"$ne": "annotated"}})

            return {
                "success": True,
                "videos": videos_data
            }
        except Exception as e:
            logger.error(f"Помилка при отриманні списку відео: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_annotation(self, azure_link: str) -> Dict[str, Any]:
        """Отримує існуючу анотацію для відео"""
        try:
            annotation_data = self.source_repo.get_annotation(azure_link)

            if not annotation_data:
                return {
                    "success": False,
                    "error": f"Анотацію для відео '{azure_link}' не знайдено"
                }

            return {
                "success": True,
                "annotation": annotation_data
            }

        except Exception as e:
            logger.error(f"Помилка при отриманні анотації: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }