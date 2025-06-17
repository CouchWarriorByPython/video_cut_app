from typing import Dict, Any, Optional

from backend.database import create_repository
from backend.services.cvat_service import CVATService
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class AnnotationService:
    """Сервіс для роботи з анотаціями"""

    def __init__(self):
        self.source_repo = create_repository("source_videos", async_mode=False)
        self.cvat_service = CVATService()

    def save_fragments_and_metadata(self, azure_link: str, annotation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Зберігає фрагменти відео та метадані"""
        try:
            skip_processing = annotation_data.get("metadata", {}).get("skip", False)

            self.source_repo.create_indexes()

            existing = self.source_repo.find_by_field("azure_link", azure_link)
            if not existing:
                return {
                    "success": False,
                    "error": f"Відео з посиланням {azure_link} не знайдено"
                }

            # Валідація мінімальної тривалості кліпів
            clips = annotation_data.get("clips", {})
            validation_error = self._validate_clips_duration(clips)
            if validation_error:
                return {
                    "success": False,
                    "error": validation_error
                }

            # Підготовка даних для оновлення
            update_data = {
                "metadata": annotation_data.get("metadata"),
                "clips": annotation_data.get("clips"),
                "status": "annotated"
            }

            # Додавання CVAT параметрів якщо відсутні
            if "cvat_params" not in existing or not existing["cvat_params"]:
                cvat_params = {}
                for clip_type in annotation_data.get("clips", {}).keys():
                    cvat_params[clip_type] = self.cvat_service.get_default_project_params(clip_type)
                update_data["cvat_params"] = cvat_params

            # Оновлення документа через новий метод
            success = self.source_repo.update_by_id(existing["_id"], update_data)

            if not success:
                return {
                    "success": False,
                    "error": "Не вдалося оновити документ"
                }

            record_id = existing["_id"]

            if skip_processing:
                success_message = "Дані успішно збережено. Обробку пропущено (skip)."
                logger.info(f"Відео пропущено (skip): {azure_link}")
                task_id = None
            else:
                success_message = "Дані успішно збережено. Обробку запущено."
                task_id = None  # Task ID буде встановлено в API layer

            return {
                "success": True,
                "_id": record_id,
                "task_id": task_id,
                "message": success_message,
                "skip_processing": skip_processing
            }

        except Exception as e:
            logger.error(f"Помилка при збереженні анотації: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _validate_clips_duration(self, clips: Dict[str, Any]) -> Optional[str]:
        """Валідує мінімальну тривалість кліпів"""
        for project_type, project_clips in clips.items():
            for clip in project_clips:
                start_parts = clip["start_time"].split(":")
                end_parts = clip["end_time"].split(":")

                start_seconds = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + int(start_parts[2])
                end_seconds = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + int(end_parts[2])

                if end_seconds - start_seconds < 1:
                    return f"Мінімальна тривалість кліпу - 1 секунда. Кліп {clip['id']} в проєкті {project_type} занадто короткий."

        return None