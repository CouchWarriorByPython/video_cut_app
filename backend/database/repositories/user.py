from typing import Dict, List, Optional
from bson import ObjectId
from passlib.context import CryptContext
from pydantic import EmailStr

from backend.database.base import AnnotationBase
from backend.database.connection import DatabaseConnection
from backend.utils.logger import get_logger

logger = get_logger(__name__, "database.log")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRepository(AnnotationBase):
    """Репозиторій для роботи з користувачами"""

    def __init__(self) -> None:
        super().__init__("users")
        self.db = DatabaseConnection.get_sync_database()
        self.collection = self.db[self.collection_name]

    def create_indexes(self) -> None:
        """Створює індекси для колекції користувачів"""
        try:
            existing_indexes = self.collection.list_indexes()
            index_names = [idx["name"] for idx in existing_indexes]

            if not any("email" in name for name in index_names):
                self.collection.create_index("email", unique=True)
                logger.debug("Створено унікальний індекс email для users")

        except Exception as e:
            logger.error(f"Помилка при роботі з індексами: {str(e)}")

    def create_user(self, email: EmailStr, password: str, role: str) -> str:
        """Створює нового користувача"""
        try:
            hashed_password = self.hash_password(password)

            user_data = {
                "email": str(email),  # Конвертуємо тільки для БД
                "hashed_password": hashed_password,
                "role": role,
                "is_active": True
            }

            data = self._prepare_annotation(user_data)
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            result = self.collection.insert_one(data_without_id)
            logger.info(f"Створено користувача: {email} з роллю {role}")
            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка створення користувача: {str(e)}")
            raise

    def get_user_by_email(self, email: EmailStr) -> Optional[Dict]:
        """Отримує користувача за email"""
        try:
            # Конвертуємо в str тільки для запиту до БД
            doc = self.collection.find_one({"email": str(email), "is_active": True})
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка отримання користувача: {str(e)}")
            raise

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Отримує користувача за ID"""
        try:
            doc = self.collection.find_one({"_id": ObjectId(user_id), "is_active": True})
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка отримання користувача: {str(e)}")
            raise

    def get_all_users(self) -> List[Dict]:
        """Отримує всіх активних користувачів"""
        try:
            docs = list(self.collection.find({"is_active": True}))
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання користувачів: {str(e)}")
            raise

    def update_user(self, user_id: str, updates: Dict) -> bool:
        """Оновлює користувача"""
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {**updates, "updated_at": self._get_current_time()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Помилка оновлення користувача: {str(e)}")
            raise

    def delete_user(self, user_id: str) -> bool:
        """Деактивує користувача (soft delete)"""
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": False, "updated_at": self._get_current_time()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Помилка видалення користувача: {str(e)}")
            raise

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Перевіряє пароль"""
        return pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        """Хешує пароль"""
        return pwd_context.hash(password)

    def _get_current_time(self) -> str:
        """Отримує поточний час"""
        from datetime import datetime
        return datetime.now().isoformat(sep=" ", timespec="seconds")