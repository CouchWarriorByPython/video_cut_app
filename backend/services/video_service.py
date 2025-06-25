import os
import math
from typing import Dict, Any, Optional, List

from backend.database import (
    create_source_video_repository,
    create_clip_video_repository
)
from backend.services.azure_service import AzureService
from backend.services.video_lock_service import VideoLockService
from backend.services.auth_service import AuthService
from backend.models.shared import AzureFilePath, VideoStatus
from backend.models.documents import AzureFilePathDocument
from backend.models.api import (
    VideoUploadResponse, VideoStatusResponse, VideoListResponse,
    LockVideoResponse, VideoInfoResponse, PaginationInfo
)
from backend.api.exceptions import (
    VideoNotFoundException, VideoNotReadyException,
    BusinessLogicException, AuthenticationException
)
from backend.utils.azure_path_utils import extract_filename_from_azure_path
from backend.utils.video_utils import get_local_video_path
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class VideoService:
    """Сервіс для операцій з відео"""

    def __init__(self) -> None:
        self.source_repo = create_source_video_repository()
        self.clip_repo = create_clip_video_repository()
        self.azure_service = AzureService()
        self.lock_service = VideoLockService()
        self.auth_service = AuthService()

    def register_single_video(self, video_url: str) -> VideoUploadResponse:
        """Реєстрація одного відео для асинхронної обробки"""
        try:
            validation_result = self.azure_service.validate_azure_url(video_url)

            if not validation_result["valid"]:
                raise BusinessLogicException(
                    f"Невалідний Azure URL: {validation_result['error']}"
                )

            azure_path = validation_result["azure_path"]
            filename = validation_result["filename"]
            size_bytes = validation_result["size_bytes"]

            existing_video = self.source_repo.get_by_field("azure_file_path.blob_path", azure_path.blob_path)
            if existing_video:
                raise BusinessLogicException(f"Відео вже зареєстровано: {filename}")

            azure_file_path_doc = AzureFilePathDocument(
                account_name=azure_path.account_name,
                container_name=azure_path.container_name,
                blob_path=azure_path.blob_path
            )

            video_document = self.source_repo.create(
                azure_file_path=azure_file_path_doc,
                status=VideoStatus.DOWNLOADING,
                size_MB=round(size_bytes / (1024 * 1024), 2) if size_bytes else None
            )

            from backend.background_tasks.tasks.video_download_conversion import download_and_convert_video
            task = download_and_convert_video.delay(azure_path.model_dump())

            logger.info(f"Відео зареєстровано та додано в чергу: {filename}, task_id: {task.id}")

            return VideoUploadResponse(
                id=str(video_document.id),
                azure_file_path=azure_path,
                filename=filename,
                conversion_task_id=task.id,
                message="Відео зареєстровано та додано в чергу обробки"
            )

        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(f"Помилка реєстрації відео: {str(e)}")
            raise BusinessLogicException(f"Помилка реєстрації відео: {str(e)}")

    def register_multiple_videos(self, video_urls: List[str]) -> VideoUploadResponse:
        """Реєстрація кількох відео з URLs"""
        try:
            results = []
            errors = []

            for url in video_urls:
                try:
                    result = self.register_single_video(url)
                    results.append({
                        "filename": result.filename,
                        "task_id": result.conversion_task_id
                    })
                except BusinessLogicException as e:
                    errors.append(f"{url}: {str(e)}")

            if not results and errors:
                raise BusinessLogicException(
                    f"Всі відео не вдалося зареєструвати:\n" + "\n".join(errors)
                )

            return VideoUploadResponse(
                id="batch_upload",
                azure_file_path=None,
                filename=f"{len(results)} відео",
                conversion_task_id=None,
                message=f"Зареєстровано {len(results)} відео з {len(video_urls)}",
                batch_results={"successful": results, "errors": errors}
            )

        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(f"Помилка реєстрації кількох відео: {str(e)}")
            raise BusinessLogicException(f"Помилка реєстрації відео: {str(e)}")

    def register_videos_from_folder(self, folder_url: str) -> VideoUploadResponse:
        """Реєстрація всіх відео з Azure папки"""
        try:
            videos_in_folder = self.azure_service.list_videos_in_folder(folder_url)

            if not videos_in_folder:
                raise BusinessLogicException("Не знайдено відео файлів у вказаній папці")

            results = []
            errors = []

            for video_info in videos_in_folder:
                try:
                    result = self.register_single_video(video_info["url"])
                    results.append({
                        "filename": result.filename,
                        "task_id": result.conversion_task_id
                    })
                except BusinessLogicException as e:
                    errors.append(f"{video_info['filename']}: {str(e)}")

            return VideoUploadResponse(
                id="folder_upload",
                azure_file_path=None,
                filename=f"Папка з {len(results)} відео",
                conversion_task_id=None,
                message=f"Зареєстровано {len(results)} відео з папки",
                batch_results={"successful": results, "errors": errors}
            )

        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(f"Помилка реєстрації відео з папки: {str(e)}")
            raise BusinessLogicException(f"Помилка реєстрації відео з папки: {str(e)}")

    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """Отримання статусу Celery завдання"""
        try:
            from backend.background_tasks.app import app
            task = app.AsyncResult(task_id)

            status_mapping = {
                'PENDING': {
                    "status": "pending",
                    "progress": 0,
                    "stage": "queued",
                    "message": "Завдання в черзі на виконання"
                },
                'SUCCESS': {
                    "status": "completed",
                    "progress": 100,
                    "stage": "completed",
                    "message": "Відео готове для анотації",
                    "result": task.result
                }
            }

            if task.state in status_mapping:
                return status_mapping[task.state]
            elif task.state == 'PROGRESS':
                return {
                    "status": "processing",
                    "progress": task.info.get('progress', 0),
                    "stage": task.info.get('stage', 'unknown'),
                    "message": task.info.get('message', 'Обробка...')
                }
            elif task.state == 'FAILURE':
                error_message = 'Невідома помилка'
                if hasattr(task, 'info') and task.info:
                    if isinstance(task.info, dict):
                        error_message = task.info.get('error', task.info.get('exc_message', str(task.info)))
                    else:
                        error_message = str(task.info)

                return {
                    "status": "failed",
                    "progress": 0,
                    "stage": "failed",
                    "message": error_message
                }
            else:
                return {
                    "status": task.state.lower(),
                    "progress": 0,
                    "stage": "unknown",
                    "message": f"Невідомий стан: {task.state}"
                }

        except Exception as e:
            logger.error(f"Помилка отримання статусу завдання {task_id}: {str(e)}")
            raise BusinessLogicException(f"Помилка отримання статусу завдання: {str(e)}")

    def get_video_status(self, azure_file_path: AzureFilePath) -> VideoStatusResponse:
        """Отримання статусу обробки відео"""
        try:
            video = self.source_repo.get_by_field("azure_file_path.blob_path", azure_file_path.blob_path)

            if not video:
                raise VideoNotFoundException()

            filename = extract_filename_from_azure_path(azure_file_path)

            return VideoStatusResponse(
                status=video.status,
                filename=filename,
                ready_for_annotation=video.status == VideoStatus.NOT_ANNOTATED
            )

        except VideoNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Помилка отримання статусу відео: {str(e)}")
            raise BusinessLogicException(f"Помилка отримання статусу відео: {str(e)}")

    def get_videos_list_paginated(self, page: int = 1, per_page: int = 20, user_id: Optional[str] = None) -> VideoListResponse:
        """Отримання пагінованого списку відео"""
        try:
            valid_statuses = [VideoStatus.NOT_ANNOTATED, VideoStatus.IN_PROGRESS, VideoStatus.ANNOTATED]
            all_videos = [v for v in self.source_repo.get_all() if v.status in valid_statuses]

            all_videos.sort(key=lambda x: x.created_at_utc, reverse=True)

            total_count = len(all_videos)
            total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

            offset = (page - 1) * per_page
            videos_for_page = all_videos[offset:offset + per_page]

            video_ids = [str(video.id) for video in videos_for_page]
            lock_statuses = self.lock_service.get_all_video_locks(video_ids)

            processed_videos = []
            for video in videos_for_page:
                video_id = str(video.id)
                lock_status = lock_statuses.get(video_id, {"locked": False})
                can_start_work = self._can_user_start_work(video, lock_status, user_id)

                # Отримуємо метадані з першого кліпу
                first_clip_data = self.clip_repo.get_all({"source_video_id": video_id}, limit=1)
                metadata = first_clip_data[0] if first_clip_data else None

                video_info = VideoInfoResponse(
                    id=video_id,
                    azure_file_path=AzureFilePath(
                        account_name=video.azure_file_path.account_name,
                        container_name=video.azure_file_path.container_name,
                        blob_path=video.azure_file_path.blob_path
                    ),
                    filename=self._get_display_filename(video),
                    status=video.status,
                    created_at_utc=video.created_at_utc.isoformat(sep=" ", timespec="seconds"),
                    where=metadata.where if metadata else None,
                    when=metadata.when if metadata else None,
                    uav_type=metadata.uav_type if metadata else None,
                    duration_sec=video.duration_sec,
                    lock_status=lock_status,
                    can_start_work=can_start_work
                )
                processed_videos.append(video_info)

            pagination = PaginationInfo(
                current_page=page,
                per_page=per_page,
                total_count=total_count,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1
            )

            return VideoListResponse(
                videos=processed_videos,
                pagination=pagination
            )

        except Exception as e:
            logger.error(f"Помилка отримання списку відео: {str(e)}")
            raise BusinessLogicException(f"Помилка отримання списку відео: {str(e)}")

    def lock_video_for_annotation(self, video_id: str, user_id: str, user_email: str) -> LockVideoResponse:
        """Блокування відео для анотації"""
        try:
            video = self.source_repo.get_by_id(video_id)
            if not video:
                raise VideoNotFoundException(video_id)

            if video.status not in [VideoStatus.NOT_ANNOTATED, VideoStatus.IN_PROGRESS]:
                raise VideoNotReadyException(video.status, "not_annotated або in_progress")

            lock_result = self.lock_service.lock_video(video_id, user_id, user_email)

            if not lock_result["success"]:
                raise BusinessLogicException(lock_result["error"])

            if lock_result["success"]:
                self.source_repo.update_by_id(video_id, {"status": VideoStatus.IN_PROGRESS})
                logger.info(f"Відео {video_id} заблоковано для анотації користувачем {user_email}")

            return LockVideoResponse(
                message=lock_result["message"],
                expires_at=lock_result.get("expires_at")
            )

        except (VideoNotFoundException, VideoNotReadyException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(f"Помилка блокування відео {video_id}: {str(e)}")
            raise BusinessLogicException(f"Помилка блокування відео: {str(e)}")

    def unlock_video_for_annotation(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """Розблокування відео"""
        try:
            unlock_result = self.lock_service.unlock_video(video_id, user_id)

            if not unlock_result["success"]:
                raise BusinessLogicException(unlock_result["error"])

            video = self.source_repo.get_by_id(video_id)
            if video and video.status == VideoStatus.IN_PROGRESS:
                self.source_repo.update_by_id(video_id, {"status": VideoStatus.NOT_ANNOTATED})

            return unlock_result

        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(f"Помилка розблокування відео {video_id}: {str(e)}")
            raise BusinessLogicException(f"Помилка розблокування відео: {str(e)}")

    def get_video_file_for_streaming(self, azure_file_path: AzureFilePath, token: str) -> Dict[str, Any]:
        """Отримання файлу відео для стрімінгу з перевіркою токена"""
        try:
            # Перевіряємо токен
            payload = self.auth_service.verify_token(token)
            if not payload:
                raise AuthenticationException("Невалідний токен")

            allowed_roles = ["annotator", "admin", "super_admin"]
            if payload.role not in allowed_roles:
                raise BusinessLogicException("Недостатньо прав для перегляду відео")

            # Отримуємо відео
            video = self.source_repo.get_by_field("azure_file_path.blob_path", azure_file_path.blob_path)
            if not video:
                raise VideoNotFoundException()

            if video.status not in [VideoStatus.NOT_ANNOTATED, VideoStatus.IN_PROGRESS]:
                raise VideoNotReadyException(video.status)

            filename = extract_filename_from_azure_path(azure_file_path)
            if not filename:
                raise BusinessLogicException("Не вдалося визначити ім'я файлу")

            local_path = get_local_video_path(filename)

            if not os.path.exists(local_path):
                raise BusinessLogicException("Локальний файл не знайдено")

            return {
                "file_path": local_path,
                "filename": filename
            }

        except (AuthenticationException, VideoNotFoundException, VideoNotReadyException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(f"Помилка отримання файлу для стрімінгу: {str(e)}")
            raise BusinessLogicException(f"Помилка отримання файлу: {str(e)}")

    @staticmethod
    def _can_user_start_work(video: Any, lock_status: Dict[str, Any], user_id: Optional[str]) -> bool:
        """Визначення чи може користувач почати роботу з відео"""
        video_status = video.status

        if video_status == VideoStatus.ANNOTATED:
            return False

        if video_status == VideoStatus.NOT_ANNOTATED:
            return not lock_status.get("locked") or (user_id and lock_status.get("user_id") == user_id)

        if video_status == VideoStatus.IN_PROGRESS:
            return user_id and lock_status.get("user_id") == user_id

        return False

    @staticmethod
    def _get_display_filename(video: Any) -> str:
        """Отримання відображуваного імені файлу"""
        if hasattr(video, 'azure_file_path') and video.azure_file_path and video.azure_file_path.blob_path:
            return video.azure_file_path.blob_path.split("/")[-1]
        return f"Video #{getattr(video, 'id', 'unknown')}"