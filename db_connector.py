from typing import Dict, List, Optional, Union, Protocol
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from configs import Settings


# Моделі даних
class ClipInfo(BaseModel):
    """Інформація про відрізок відео"""
    id: int
    start_time: str
    end_time: str


class VideoMetadata(BaseModel):
    """Метадані відео"""
    skip: bool = False
    uav_type: str = ""
    video_content: str = ""
    is_urban: bool = False
    has_osd: bool = False
    is_analog: bool = False
    night_video: bool = False
    multiple_streams: bool = False
    has_infantry: bool = False
    has_explosions: bool = False


class VideoAnnotation(BaseModel):
    """Повна модель анотації відео"""
    source: str
    metadata: VideoMetadata
    clips: Dict[str, List[ClipInfo]]


# Базовий протокол (інтерфейс) для спільного API
class AnnotationRepositoryProtocol(Protocol):
    """Інтерфейс для роботи з анотаціями відео в MongoDB"""

    def create_indexes(self):
        """Створення необхідних індексів для колекції"""
        ...

    def save_annotation(self, annotation):
        """
        Збереження анотації (створення нової або оновлення існуючої)

        Args:
            annotation: Дані анотації у форматі dict або VideoAnnotation

        Returns:
            str: ID документа або повідомлення про успішне оновлення
        """
        ...

    def get_annotation(self, source):
        """
        Отримання анотації за ідентифікатором відео

        Args:
            source: Ідентифікатор відео

        Returns:
            Optional[Dict]: Документ анотації або None, якщо не знайдено
        """
        ...

    def get_all_annotations(self):
        """
        Отримання всіх анотацій

        Returns:
            List[Dict]: Список документів анотацій
        """
        ...

    def delete_annotation(self, source):
        """
        Видалення анотації за ідентифікатором відео

        Args:
            source: Ідентифікатор відео

        Returns:
            bool: True, якщо видалення виконано успішно
        """
        ...

    def close(self):
        """Закриття з'єднання з MongoDB"""
        ...


# Синхронна реалізація для Celery та скриптів
class SyncVideoAnnotationRepository:
    """Синхронний репозиторій для збереження відео-анотацій в MongoDB"""

    def __init__(self, collection_name=None):
        self.client = MongoClient(Settings.mongo_uri)
        self.db = self.client[Settings.mongo_db_name]
        self.collection = self.db[collection_name]

    def create_indexes(self):
        self.collection.create_index("source", unique=True)

    def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        # Перетворення Pydantic моделі в словник, якщо потрібно
        if isinstance(annotation, VideoAnnotation):
            annotation = annotation.model_dump()

        source = annotation.get("source")
        if not source:
            raise ValueError("Анотація повинна містити поле 'source'")

        # Перевіряємо, чи існує документ з таким source
        existing = self.collection.find_one({"source": source})

        if existing:
            # Якщо документ існує - оновлюємо його повністю
            self.collection.replace_one({"source": source}, annotation)
            return f"Документ з source={source} оновлено"
        else:
            # Якщо документ не існує - створюємо новий
            result = self.collection.insert_one(annotation)
            return str(result.inserted_id)

    def get_annotation(self, source: str) -> Optional[Dict]:
        return self.collection.find_one({"source": source})

    def get_all_annotations(self) -> List[Dict]:
        return list(self.collection.find())

    def delete_annotation(self, source: str) -> bool:
        result = self.collection.delete_one({"source": source})
        return result.deleted_count > 0

    def close(self):
        self.client.close()


# Асинхронна реалізація для FastAPI
class AsyncVideoAnnotationRepository:
    """Асинхронний репозиторій для збереження відео-анотацій в MongoDB"""

    def __init__(self, collection_name: str):
        self.client = AsyncIOMotorClient(Settings.mongo_uri)
        self.db = self.client[Settings.mongo_db_name]
        self.collection = self.db[collection_name]

    async def create_indexes(self):
        await self.collection.create_index("source", unique=True)

    async def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        # Перетворення Pydantic моделі в словник, якщо потрібно
        if isinstance(annotation, VideoAnnotation):
            annotation = annotation.model_dump()

        source = annotation.get("source")
        if not source:
            raise ValueError("Анотація повинна містити поле 'source'")

        # Перевіряємо, чи існує документ з таким source
        existing = await self.collection.find_one({"source": source})

        if existing:
            # Якщо документ існує - оновлюємо його повністю
            await self.collection.replace_one({"source": source}, annotation)
            return f"Документ з source={source} оновлено"
        else:
            # Якщо документ не існує - створюємо новий
            result = await self.collection.insert_one(annotation)
            return str(result.inserted_id)

    async def get_annotation(self, source: str) -> Optional[Dict]:
        return await self.collection.find_one({"source": source})

    async def get_all_annotations(self) -> List[Dict]:
        cursor = self.collection.find()
        return await cursor.to_list(length=None)

    async def delete_annotation(self, source: str) -> bool:
        result = await self.collection.delete_one({"source": source})
        return result.deleted_count > 0

    def close(self):
        self.client.close()


# Фабрика для створення потрібної реалізації
def create_repository(collection_name: str, async_mode: bool = False):
    """
    Створення репозиторію для роботи з MongoDB

    Args:
        async_mode: Використовувати асинхронну реалізацію (True) або синхронну (False)
        collection_name: Назва колекції в MongoDB (опціонально)

    Returns:
        Об'єкт репозиторію для роботи з анотаціями відео
    """
    if async_mode:
        return AsyncVideoAnnotationRepository(collection_name=collection_name)
    else:
        return SyncVideoAnnotationRepository(collection_name=collection_name)