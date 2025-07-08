from typing import Dict, Any, List
from passlib.context import CryptContext
from pydantic import EmailStr
from datetime import datetime

from backend.database import (
    create_user_repository, create_source_video_repository,
    create_cvat_settings_repository
)
from backend.models.shared import UserRole, CVATSettings
from backend.models.api import (
    AdminStatsResponse, UserResponse, UserCreateResponse,
    UserDeleteResponse
)
from backend.api.exceptions import (
    raise_not_found, raise_business_error, raise_permission_error,
    ConflictException, ValidationException, NotFoundException, BusinessLogicException
)
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminService:
    """Service for administrative operations and user management"""

    def __init__(self):
        self.user_repo = create_user_repository()
        self.video_repo = create_source_video_repository()
        self.cvat_settings_repo = create_cvat_settings_repository()
        # Імпорт тут, щоб уникнути циклічної залежності
        from backend.services.video_lock_service import VideoLockService
        self.lock_service = VideoLockService()

    def get_system_statistics_response(self) -> AdminStatsResponse:
        """Get system statistics in API response format"""
        try:
            all_users = self.user_repo.get_all()
            total_users = len(all_users)
            active_users = len([u for u in all_users if u.is_active])

            all_videos = self.video_repo.get_all()
            total_videos = len(all_videos)
            processing_videos = len([v for v in all_videos if v.status in ["downloading", "in_progress"]])
            annotated_videos = len([v for v in all_videos if v.status == "annotated"])

            return AdminStatsResponse(
                total_users=total_users,
                active_users=active_users,
                total_videos=total_videos,
                processing_videos=processing_videos,
                annotated_videos=annotated_videos
            )

        except Exception as e:
            logger.error(f"Error getting system statistics: {str(e)}")
            raise BusinessLogicException(f"Помилка отримання статистики: {str(e)}")

    def get_all_users_response(self) -> List[UserResponse]:
        """Get all users in API response format"""
        try:
            users = self.user_repo.get_all()

            return [
                UserResponse(
                    id=str(user.id),
                    email=user.email,
                    role=user.role,
                    created_at_utc=user.created_at_utc.isoformat(sep=" ", timespec="seconds"),
                    is_active=user.is_active
                )
                for user in users
            ]

        except Exception as e:
            logger.error(f"Error getting users: {str(e)}")
            raise_business_error(f"Помилка отримання користувачів: {str(e)}")

    def create_user_with_validation(self, email: EmailStr, password: str, role: str,
                                   current_user_role: str) -> UserCreateResponse:
        """Create user with full validation and exception handling"""
        try:
            if not self._validate_role_creation(role, current_user_role):
                raise_permission_error(current_user_role, f"створювати {role}")

            if self.user_repo.exists(email=str(email)):
                raise ConflictException(
                    message="Користувач з таким email вже існує",
                    details={"email": str(email)}
                )

            if len(password) < 8:
                raise ValidationException(
                    message="Пароль повинен містити мінімум 8 символів",
                    details={"field": "password", "min_length": 8}
                )

            user = self.user_repo.create(
                email=str(email),
                hashed_password=pwd_context.hash(password),
                role=role,
                is_active=True
            )

            logger.info(f"User created: {email} with role {role}")

            return UserCreateResponse(
                success=True,
                message=f"Користувача {email} створено успішно",
                user_id=str(user.id)
            )

        except (ConflictException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise_business_error(f"Помилка створення користувача: {str(e)}")

    def update_user_with_validation(self, user_id: str, email: EmailStr = None,
                                  password: str = None, role: str = None,
                                  current_user_id: str = None,
                                  current_user_role: str = None) -> Dict[str, Any]:
        """Update user with full validation and exception handling"""
        try:
            user_to_update = self.user_repo.get_by_id(user_id)
            if not user_to_update:
                raise_not_found("Користувач", user_id)

            if user_id == current_user_id:
                raise_business_error("Не можна редагувати самого себе")

            # Заборона редагування супер адмінів один одним
            if (current_user_role == UserRole.SUPER_ADMIN.value and 
                user_to_update.role == UserRole.SUPER_ADMIN.value):
                raise_business_error("Супер адміни не можуть редагувати один одного")

            updates = {}

            if email and email != user_to_update.email:
                existing_user = self.user_repo.get_by_field("email", str(email))
                if existing_user and str(existing_user.id) != user_id:
                    raise ConflictException(
                        message="Користувач з таким email вже існує",
                        details={"email": str(email)}
                    )
                updates["email"] = str(email)

            if role and role != user_to_update.role:
                if not self._validate_role_update(role, current_user_role, user_to_update.role):
                    raise_permission_error(current_user_role, f"змінювати роль на {role}")
                updates["role"] = role

            if password:
                if len(password) < 8:
                    raise ValidationException(
                        message="Пароль повинен містити мінімум 8 символів",
                        details={"field": "password", "min_length": 8}
                    )
                updates["hashed_password"] = pwd_context.hash(password)

            if not updates:
                return {"success": True, "message": "Немає змін для оновлення"}

            success = self.user_repo.update_by_id(user_id, updates)

            if not success:
                raise_business_error("Помилка оновлення користувача")

            logger.info(f"User updated: {user_to_update.email}")

            return {"success": True, "message": "Користувача успішно оновлено"}

        except (NotFoundException, ConflictException, ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            raise_business_error(f"Помилка оновлення користувача: {str(e)}")

    def delete_user_with_validation(self, user_id: str, current_user_id: str,
                                  current_user_role: str) -> UserDeleteResponse:
        """Delete user with full validation and exception handling"""
        try:
            user_to_delete = self.user_repo.get_by_id(user_id)
            if not user_to_delete:
                raise_not_found("Користувач", user_id)

            if user_id == current_user_id:
                raise_business_error("Не можна видалити самого себе")

            # Заборона видалення супер адмінів один одним
            if (current_user_role == UserRole.SUPER_ADMIN.value and 
                user_to_delete.role == UserRole.SUPER_ADMIN.value):
                raise_business_error("Супер адміни не можуть видаляти один одного")

            if not self._validate_user_deletion(user_to_delete.role, current_user_role):
                raise_permission_error(current_user_role, f"видаляти {user_to_delete.role}")

            success = self.user_repo.delete_by_id(user_id)

            if not success:
                raise_business_error("Помилка видалення користувача")

            logger.info(f"User deleted: {user_to_delete.email}")

            return UserDeleteResponse(
                success=True,
                message="Користувача успішно видалено"
            )

        except (NotFoundException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}")
            raise_business_error(f"Помилка видалення користувача: {str(e)}")

    def get_cvat_settings_response(self) -> List[CVATSettings]:
        """Get CVAT settings in API response format"""
        try:
            self._initialize_default_cvat_settings()
            all_settings = self.cvat_settings_repo.get_all()

            return [
                CVATSettings(
                    project_name=setting.project_name,
                    project_id=setting.project_id,
                    overlap=setting.overlap,
                    segment_size=setting.segment_size,
                    image_quality=setting.image_quality
                )
                for setting in all_settings
            ]

        except Exception as e:
            logger.error(f"Error getting CVAT settings: {str(e)}")
            raise_business_error(f"Помилка отримання налаштувань CVAT: {str(e)}")

    @staticmethod
    def update_cvat_settings_with_model(settings: CVATSettings) -> Dict[str, Any]:
        """Update CVAT settings with full validation using CVATSettings model"""
        try:
            from backend.services.cvat_service import CVATService
            cvat_service = CVATService()

            # Additional validation for project_id conflicts
            existing_with_same_id = cvat_service.settings_repo.get_by_field("project_id", settings.project_id)
            if existing_with_same_id and existing_with_same_id.project_name != settings.project_name.value:
                project_names = {
                    'motion_detection': 'Motion Detection',
                    'military_targets_detection_and_tracking_moving': 'Military Targets Moving',
                    'military_targets_detection_and_tracking_static': 'Military Targets Static',
                    're_id': 'Re-identification'
                }
                current_project_name = project_names.get(existing_with_same_id.project_name, existing_with_same_id.project_name)
                raise_business_error(f"Project ID {settings.project_id} вже використовується проєктом '{current_project_name}'. Будь ласка, оберіть інший ID.")

            success = cvat_service.update_project_settings(settings)

            if not success:
                raise_business_error("Помилка оновлення налаштувань. Спробуйте ще раз.")

            return {
                "success": True,
                "message": "Налаштування успішно оновлені"
            }

        except Exception as e:
            logger.error(f"Error updating CVAT settings: {str(e)}")
            # Передаємо оригінальну помилку, якщо вона вже інформативна
            if "вже використовується" in str(e):
                raise_business_error(str(e))
            else:
                raise_business_error(f"Помилка оновлення налаштувань CVAT: {str(e)}")

    @staticmethod
    def _validate_role_creation(role: str, current_user_role: str) -> bool:
        """Validate if current user can create user with specified role"""
        if current_user_role == UserRole.SUPER_ADMIN.value:
            return role in [UserRole.ANNOTATOR.value, UserRole.ADMIN.value]
        elif current_user_role == UserRole.ADMIN.value:
            return role == UserRole.ANNOTATOR.value
        return False

    @staticmethod
    def _validate_role_update(new_role: str, current_user_role: str, target_user_role: str) -> bool:
        """Validate if current user can update target user's role"""
        if current_user_role == UserRole.SUPER_ADMIN:
            return new_role in [UserRole.ANNOTATOR, UserRole.ADMIN]
        elif current_user_role == UserRole.ADMIN:
            return new_role == UserRole.ANNOTATOR and target_user_role != UserRole.ADMIN
        return False

    @staticmethod
    def _validate_user_deletion(target_user_role: str, current_user_role: str) -> bool:
        """Validate if current user can delete target user"""
        if current_user_role == UserRole.ANNOTATOR:
            return False
        elif current_user_role == UserRole.ADMIN:
            return target_user_role == UserRole.ANNOTATOR
        elif current_user_role == UserRole.SUPER_ADMIN:
            return target_user_role in [UserRole.ANNOTATOR, UserRole.ADMIN]
        return False

    def initialize_default_cvat_settings(self) -> None:
        """Initialize default CVAT settings if they don't exist"""
        try:
            default_settings = [
                {"project_name": "motion_detection", "project_id": 5, "overlap": 5, "segment_size": 400,
                 "image_quality": 100},
                {"project_name": "military_targets_detection_and_tracking_moving", "project_id": 6, "overlap": 5, "segment_size": 400, "image_quality": 100},
                {"project_name": "military_targets_detection_and_tracking_static", "project_id": 7, "overlap": 5, "segment_size": 400,
                 "image_quality": 100},
                {"project_name": "re_id", "project_id": 8, "overlap": 5, "segment_size": 400, "image_quality": 100},
            ]

            for settings_data in default_settings:
                existing = self.cvat_settings_repo.get_by_field("project_name", settings_data["project_name"])
                if not existing:
                    self.cvat_settings_repo.create(**settings_data)
                    logger.info(f"Initialized default CVAT settings for {settings_data['project_name']}")

        except Exception as e:
            logger.error(f"Error initializing CVAT settings: {str(e)}")
            raise

    def _initialize_default_cvat_settings(self) -> None:
        """Private wrapper for backward compatibility"""
        self.initialize_default_cvat_settings()

    def reset_cvat_settings_to_defaults(self) -> Dict[str, Any]:
        """Reset all CVAT settings to default values"""
        try:
            default_settings = [
                {"project_name": "motion_detection", "project_id": 5, "overlap": 5, "segment_size": 400,
                 "image_quality": 100},
                {"project_name": "military_targets_detection_and_tracking_moving", "project_id": 6, "overlap": 5, "segment_size": 400, "image_quality": 100},
                {"project_name": "military_targets_detection_and_tracking_static", "project_id": 7, "overlap": 5, "segment_size": 400,
                 "image_quality": 100},
                {"project_name": "re_id", "project_id": 8, "overlap": 5, "segment_size": 400, "image_quality": 100},
            ]

            reset_count = 0
            for settings_data in default_settings:
                existing = self.cvat_settings_repo.get_by_field("project_name", settings_data["project_name"])
                if existing:
                    # Update existing settings to default values
                    success = self.cvat_settings_repo.update_by_id(
                        str(existing.id),
                        {
                            "project_id": settings_data["project_id"],
                            "overlap": settings_data["overlap"],
                            "segment_size": settings_data["segment_size"],
                            "image_quality": settings_data["image_quality"]
                        }
                    )
                    if success:
                        reset_count += 1
                        logger.info(f"Reset CVAT settings for {settings_data['project_name']} to defaults")
                else:
                    # Create new settings with default values
                    self.cvat_settings_repo.create(**settings_data)
                    reset_count += 1
                    logger.info(f"Created default CVAT settings for {settings_data['project_name']}")

            return {
                "success": True,
                "message": f"Скинуто {reset_count} CVAT налаштувань до дефолтних значень"
            }

        except Exception as e:
            logger.error(f"Error resetting CVAT settings: {str(e)}")
            raise_business_error(f"Помилка скидання CVAT налаштувань: {str(e)}")

    def fix_orphaned_in_progress_videos(self) -> Dict[str, Any]:
        """Виправити відео зі статусом IN_PROGRESS, які не заблоковані"""
        try:
            # Отримуємо всі відео зі статусом IN_PROGRESS
            all_videos = self.video_repo.get_all()
            in_progress_videos = [v for v in all_videos if v.status == "in_progress"]
            
            if not in_progress_videos:
                return {
                    "success": True,
                    "message": "No IN_PROGRESS videos found",
                    "fixed_count": 0
                }
                
            video_ids = [str(video.id) for video in in_progress_videos]
            lock_statuses = self.lock_service.get_all_video_locks(video_ids)
            
            fixed_count = 0
            for video in in_progress_videos:
                video_id = str(video.id)
                lock_status = lock_statuses.get(video_id, {"locked": False})
                
                # Якщо відео має статус IN_PROGRESS, але не заблоковане - виправляємо
                if not lock_status.get("locked"):
                    self.video_repo.update_by_id(video_id, {"status": "not_annotated"})
                    logger.info(f"Fixed orphaned IN_PROGRESS video {video_id} -> NOT_ANNOTATED")
                    fixed_count += 1
                    
            return {
                "success": True,
                "message": f"Fixed {fixed_count} orphaned IN_PROGRESS videos",
                "fixed_count": fixed_count,
                "total_in_progress": len(in_progress_videos)
            }
            
        except Exception as e:
            logger.error(f"Error fixing orphaned IN_PROGRESS videos: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def delete_video(self, video_id: str) -> Dict[str, Any]:
        """Видалити відео (локальний файл + запис з БД)"""
        try:
            # Отримуємо відео з бази
            video = self.video_repo.get_by_id(video_id)
            if not video:
                return {
                    "success": False,
                    "error": "Відео не знайдено"
                }

            # Видаляємо локальний файл якщо існує
            from backend.utils.azure_path_utils import extract_filename_from_azure_path
            from backend.utils.video_utils import get_local_video_path
            import os

            filename = extract_filename_from_azure_path(video.azure_file_path)
            if filename:
                local_path = get_local_video_path(filename)
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                        logger.info(f"Deleted local video file: {local_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete local file {local_path}: {str(e)}")

            # Видаляємо всі пов'язані кліпи
            from backend.database import create_clip_video_repository
            clip_repo = create_clip_video_repository()
            clips = clip_repo.get_all({"source_video_id": video_id})
            deleted_clips = 0
            for clip in clips:
                clip.delete()
                deleted_clips += 1

            # Видаляємо блокування з Redis якщо є
            try:
                lock_status = self.lock_service.get_video_lock_status(video_id)
                if lock_status.get("locked"):
                    self.lock_service.unlock_video(video_id, lock_status.get("user_id", ""))
            except Exception as e:
                logger.warning(f"Failed to unlock video {video_id}: {str(e)}")

            # Видаляємо запис з бази
            success = self.video_repo.delete_by_id(video_id)
            if not success:
                return {
                    "success": False,
                    "error": "Помилка видалення з бази даних"
                }

            logger.info(f"Video {video_id} completely deleted (including {deleted_clips} clips)")
            
            return {
                "success": True,
                "message": f"Відео успішно видалено (включно з {deleted_clips} кліпами)",
                "deleted_clips": deleted_clips
            }

        except Exception as e:
            logger.error(f"Error deleting video {video_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_admin_videos_list(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Отримати список всіх відео для адмінів"""
        try:
            # Отримуємо всі відео (без фільтрації за статусом)
            all_videos = self.video_repo.get_all()
            all_videos.sort(key=lambda x: x.created_at_utc, reverse=True)

            total_count = len(all_videos)
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

            offset = (page - 1) * per_page
            videos_for_page = all_videos[offset:offset + per_page]

            # Отримуємо статуси блокування
            video_ids = [str(video.id) for video in videos_for_page]
            lock_statuses = self.lock_service.get_all_video_locks(video_ids)

            # Формуємо відповідь
            videos_info = []
            for video in videos_for_page:
                video_id = str(video.id)
                lock_status = lock_statuses.get(video_id, {"locked": False})
                
                # Отримуємо ім'я файлу
                from backend.utils.azure_path_utils import extract_filename_from_azure_path
                filename = extract_filename_from_azure_path(video.azure_file_path)
                
                # Перевіряємо чи існує локальний файл
                from backend.utils.video_utils import get_local_video_path
                import os
                local_exists = False
                if filename:
                    local_path = get_local_video_path(filename)
                    local_exists = os.path.exists(local_path)

                video_info = {
                    "id": video_id,
                    "filename": filename or f"Video #{video_id}",
                    "status": video.status,
                    "created_at": video.created_at_utc.isoformat(sep=" ", timespec="seconds"),
                    "size_mb": getattr(video, 'size_MB', None),
                    "duration_sec": getattr(video, 'duration_sec', None),
                    "lock_status": lock_status,
                    "local_file_exists": local_exists,
                    "azure_path": {
                        "account_name": video.azure_file_path.account_name,
                        "container_name": video.azure_file_path.container_name,
                        "blob_path": video.azure_file_path.blob_path
                    }
                }
                videos_info.append(video_info)

            return {
                "success": True,
                "videos": videos_info,
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }

        except Exception as e:
            logger.error(f"Error getting admin videos list: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_system_health_info(self) -> Dict[str, Any]:
        """Отримати діагностичну інформацію про стан системи"""
        try:
            health_info = {
                "timestamp": datetime.now().isoformat(),
                "redis": {},
                "mongodb": {},
                "users": {},
                "videos": {}
            }
            
            # Redis health check
            try:
                redis_info = self.lock_service.get_redis_health_info()
                health_info["redis"] = redis_info
            except Exception as e:
                health_info["redis"] = {"error": f"Redis check failed: {str(e)}"}
            
            # MongoDB health check
            try:
                total_users = len(self.user_repo.get_all())
                total_videos = len(self.video_repo.get_all())
                
                # Перевірка з'єднання
                from backend.database.connection import DatabaseConnection
                connection_status = DatabaseConnection.is_connected()
                
                health_info["mongodb"] = {
                    "connected": connection_status,
                    "total_users": total_users,
                    "total_videos": total_videos
                }
                
            except Exception as e:
                health_info["mongodb"] = {"error": f"MongoDB check failed: {str(e)}"}
            
            # Users info
            try:
                users = self.user_repo.get_all()
                active_users = [u for u in users if u.is_active]
                inactive_users = [u for u in users if not u.is_active]
                
                health_info["users"] = {
                    "total": len(users),
                    "active": len(active_users),
                    "inactive": len(inactive_users),
                    "by_role": {}
                }
                
                # Count by roles
                for role in ["super_admin", "admin", "annotator"]:
                    role_users = [u for u in users if u.role == role]
                    health_info["users"]["by_role"][role] = len(role_users)
                    
            except Exception as e:
                health_info["users"] = {"error": f"Users check failed: {str(e)}"}
            
            # Videos info
            try:
                videos = self.video_repo.get_all()
                
                status_counts = {}
                for video in videos:
                    status = video.status
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                health_info["videos"] = {
                    "total": len(videos),
                    "by_status": status_counts
                }
                
            except Exception as e:
                health_info["videos"] = {"error": f"Videos check failed: {str(e)}"}
            
            return health_info
            
        except Exception as e:
            logger.error(f"Error getting system health info: {str(e)}")
            return {
                "error": f"System health check failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def cleanup_video_locks(self) -> Dict[str, Any]:
        """Очистити застарілі блокування відео"""
        try:
            cleaned_count = self.lock_service.cleanup_expired_locks()
            
            logger.info(f"Video locks cleanup completed: {cleaned_count} locks cleaned")
            
            return {
                "success": True,
                "message": f"Очищено {cleaned_count} застарілих блокувань",
                "cleaned_locks": cleaned_count
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up video locks: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def force_cleanup_all_locks(self) -> Dict[str, Any]:
        """Примусове видалення всіх блокувань відео"""
        try:
            result = self.lock_service.force_cleanup_all_locks()
            
            if result["success"]:
                # Також скидаємо статуси всіх відео з IN_PROGRESS на NOT_ANNOTATED
                videos = self.video_repo.get_all()
                in_progress_videos = [v for v in videos if v.status == "in_progress"]
                
                reset_count = 0
                for video in in_progress_videos:
                    self.video_repo.update_by_id(str(video.id), {"status": "not_annotated"})
                    reset_count += 1
                
                logger.warning(f"Force cleanup completed: {result['deleted_locks']} locks deleted, {reset_count} videos reset")
                
                result["reset_videos"] = reset_count
                result["message"] += f" та скинуто статус {reset_count} відео"
            
            return result
            
        except Exception as e:
            logger.error(f"Error in force cleanup: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
