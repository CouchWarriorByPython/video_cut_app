from typing import Dict, Any, List
from passlib.context import CryptContext
from pydantic import EmailStr

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

            if not self._validate_user_deletion(user_to_delete.role, current_user_role):
                raise_permission_error(current_user_role, f"видаляти {user_to_delete.role}")

            if user_id == current_user_id:
                raise_business_error("Не можна видалити самого себе")

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

            success = cvat_service.update_project_settings(settings)

            if not success:
                raise_business_error("Помилка оновлення налаштувань")

            return {
                "success": True,
                "message": "Налаштування успішно оновлені"
            }

        except Exception as e:
            logger.error(f"Error updating CVAT settings: {str(e)}")
            raise_business_error(f"Помилка оновлення налаштувань CVAT: {str(e)}")

    @staticmethod
    def _validate_role_creation(role: str, current_user_role: str) -> bool:
        """Validate if current user can create user with specified role"""
        if current_user_role == UserRole.SUPER_ADMIN:
            return role in [UserRole.ANNOTATOR, UserRole.ADMIN]
        elif current_user_role == UserRole.ADMIN:
            return role == UserRole.ANNOTATOR
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
                {"project_name": "motion-det", "project_id": 5, "overlap": 5, "segment_size": 400,
                 "image_quality": 100},
                {"project_name": "tracking", "project_id": 6, "overlap": 5, "segment_size": 400, "image_quality": 100},
                {"project_name": "mil-hardware", "project_id": 7, "overlap": 5, "segment_size": 400,
                 "image_quality": 100},
                {"project_name": "re-id", "project_id": 8, "overlap": 5, "segment_size": 400, "image_quality": 100},
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
