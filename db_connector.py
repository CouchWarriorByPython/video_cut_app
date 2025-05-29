from typing import Dict, List, Optional, Union
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId

from configs import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


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


class CVATProjectParams(BaseModel):
    """Параметри проєкту CVAT"""
    project_id: int
    overlap: int
    segment_size: int
    image_quality: int


class SourceVideoAnnotation(BaseModel):
    """Модель анотації соурс відео"""
    azure_link: str
    filename: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    when: Optional[str] = None
    where: Optional[str] = None
    status: str = "not_annotated"
    metadata: Optional[VideoMetadata] = None
    clips: Dict[str, List[ClipInfo]] = Field(default_factory=dict)
    cvat_params: Dict[str, CVATProjectParams] = Field(default_factory=dict)


class VideoClipRecord(BaseModel):
    """Модель запису відео кліпу"""
    source_id: str
    project: str
    clip_id: int
    extension: str = "mp4"
    cvat_task_id: Optional[str] = None
    status: str = "not_annotated"
    azure_link: str
    fps: int = 60
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(sep=" ", timespec="seconds"))


class AnnotationBase:
    """Базовий клас для роботи з анотаціями відео"""

    def __init__(self, collection_name: str) -> None:
        """Ініціалізує клас з вказаною колекцією"""
        self.collection_name = collection_name
        logger.info(f"Ініціалізація репозиторію для колекції: {collection_name}")

    def _prepare_annotation(self, annotation: Union[Dict, BaseModel]) -> Dict:
        """Підготовка даних анотації до збереження"""
        if isinstance(annotation, BaseModel):
            annotation = annotation.model_dump()

        annotation["updated_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")

        if self.collection_name == "source_videos" and "azure_link" not in annotation:
            raise ValueError("Анотація соурс відео повинна містити поле 'azure_link'")

        if self.collection_name == "video_clips":
            required_fields = ["source_id", "project", "clip_id", "azure_link"]
            for field in required_fields:
                if field not in annotation:
                    raise ValueError(f"Анотація кліпу повинна містити поле '{field}'")

        return annotation

    @staticmethod
    def _normalize_document(doc: Optional[Dict]) -> Optional[Dict]:
        """Перетворює MongoDB документ у звичайний словник з плоскою структурою"""
        if not doc:
            return None

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)

        return doc

    def _normalize_documents(self, docs: List[Dict]) -> List[Dict]:
        """Нормалізує список документів"""
        return [self._normalize_document(doc) for doc in docs]


class SyncVideoAnnotationRepository(AnnotationBase):
    """Синхронний репозиторій для збереження відеоанотацій в MongoDB"""

    def __init__(self, collection_name: str) -> None:
        """Ініціалізує репозиторій з вказаною колекцією"""
        super().__init__(collection_name)
        try:
            self.client = MongoClient(Settings.mongo_uri)
            self.db = self.client[Settings.mongo_db_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"Успішне підключення до MongoDB: {Settings.mongo_db_name}.{self.collection_name}")
        except Exception as e:
            logger.error(f"Помилка підключення до MongoDB: {str(e)}")
            raise

    def create_indexes(self) -> None:
        """Створює оптимальні індекси для колекції"""
        try:
            existing_indexes = self.collection.list_indexes()
            index_names = [idx["name"] for idx in existing_indexes]

            if self.collection_name == "source_videos":
                if not any("azure_link" in name for name in index_names):
                    self.collection.create_index("azure_link", unique=True)
                    logger.info("Створено унікальний індекс azure_link для source_videos")
                else:
                    logger.info("Індекс azure_link для source_videos вже існує")

            elif self.collection_name == "video_clips":
                compound_exists = any("source_id_1_project_1_clip_id_1" in name for name in index_names)
                if not compound_exists:
                    self.collection.create_index([
                        ("source_id", 1),
                        ("project", 1),
                        ("clip_id", 1)
                    ], unique=True)
                    logger.info("Створено унікальний складний індекс для video_clips")
                else:
                    logger.info("Унікальний складний індекс для video_clips вже існує")

                if not any("azure_link" in name for name in index_names):
                    self.collection.create_index("azure_link", unique=False)
                    logger.info("Створено індекс azure_link для швидкого пошуку")
                else:
                    logger.info("Індекс azure_link для пошуку вже існує")

        except Exception as e:
            logger.error(f"Помилка при роботі з індексами: {str(e)}")

    def save_annotation(self, annotation: Union[Dict, BaseModel]) -> str:
        """Зберігає або оновлює анотацію з оптимізованою логікою"""
        try:
            data = self._prepare_annotation(annotation)
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            if self.collection_name == "source_videos":
                azure_link = data.get("azure_link")
                existing = self.collection.find_one({"azure_link": azure_link})

                if existing:
                    data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                    self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                    logger.info(f"Оновлено соурс відео: {azure_link}")
                    return str(existing["_id"])
                else:
                    result = self.collection.insert_one(data_without_id)
                    logger.info(f"Створено нове соурс відео: {azure_link}")
                    return str(result.inserted_id)

            elif self.collection_name == "video_clips":
                source_id = data.get("source_id")
                project = data.get("project")
                clip_id = data.get("clip_id")

                source_id_obj = ObjectId(source_id) if isinstance(source_id, str) else source_id
                data_without_id["source_id"] = source_id_obj

                existing = self.collection.find_one({
                    "source_id": source_id_obj,
                    "project": project,
                    "clip_id": clip_id
                })

                if existing:
                    data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                    self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                    logger.info(f"Оновлено кліп: {project} clip_id={clip_id}")
                    return str(existing["_id"])
                else:
                    result = self.collection.insert_one(data_without_id)
                    logger.info(f"Створено новий кліп: {project} clip_id={clip_id}")
                    return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка збереження анотації: {str(e)}")
            raise

    def get_annotation(self, identifier: str) -> Optional[Dict]:
        """Отримує анотацію за ідентифікатором"""
        try:
            if self.collection_name == "source_videos":
                doc = self.collection.find_one({"azure_link": identifier})
                if doc:
                    logger.info(f"Знайдено соурс відео: {identifier}")
                else:
                    logger.warning(f"Соурс відео не знайдено: {identifier}")
            else:
                doc = self.collection.find_one({"_id": ObjectId(identifier)})
                if doc:
                    logger.info(f"Знайдено кліп: {identifier}")
                else:
                    logger.warning(f"Кліп не знайдено: {identifier}")

            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка отримання анотації: {str(e)}")
            raise

    def get_clips_by_source_id(self, source_id: str) -> List[Dict]:
        """Отримує всі кліпи для вказаного соурс відео"""
        try:
            source_id_obj = ObjectId(source_id)
            docs = list(self.collection.find({"source_id": source_id_obj}))
            logger.info(f"Знайдено {len(docs)} кліпів для source_id: {source_id}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання кліпів: {str(e)}")
            raise

    def get_clips_by_azure_link(self, azure_link: str) -> List[Dict]:
        """Отримує всі кліпи за Azure лінком соурс відео"""
        try:
            source_doc = self.collection.find_one({"azure_link": azure_link})
            if not source_doc:
                logger.warning(f"Соурс відео не знайдено: {azure_link}")
                return []

            source_id = source_doc["_id"]
            clips_repo = SyncVideoAnnotationRepository("video_clips")
            docs = list(clips_repo.collection.find({"source_id": source_id}))
            logger.info(f"Знайдено {len(docs)} кліпів для azure_link: {azure_link}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання кліпів за azure_link: {str(e)}")
            raise

    def get_all_annotations(self, filter_query: Optional[Dict] = None) -> List[Dict]:
        """Отримує всі анотації з можливістю фільтрації"""
        try:
            query = filter_query or {}
            docs = list(self.collection.find(query))
            logger.info(f"Отримано {len(docs)} записів з колекції {self.collection_name}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання всіх анотацій: {str(e)}")
            raise

    def delete_annotation(self, identifier: str) -> bool:
        """Видаляє анотацію за ідентифікатором"""
        try:
            if self.collection_name == "source_videos":
                result = self.collection.delete_one({"azure_link": identifier})
            else:
                result = self.collection.delete_one({"_id": ObjectId(identifier)})

            success = result.deleted_count > 0
            if success:
                logger.info(f"Видалено запис: {identifier}")
            else:
                logger.warning(f"Запис для видалення не знайдено: {identifier}")
            return success
        except Exception as e:
            logger.error(f"Помилка видалення анотації: {str(e)}")
            raise

    def close(self) -> None:
        """Закриває з'єднання з MongoDB"""
        try:
            self.client.close()
            logger.info("З'єднання з MongoDB закрито")
        except Exception as e:
            logger.error(f"Помилка закриття з'єднання: {str(e)}")


class AsyncVideoAnnotationRepository(AnnotationBase):
    """Асинхронний репозиторій для збереження відеоанотацій в MongoDB"""

    def __init__(self, collection_name: str) -> None:
        """Ініціалізує репозиторій з вказаною колекцією"""
        super().__init__(collection_name)
        try:
            self.client = AsyncIOMotorClient(Settings.mongo_uri)
            self.db = self.client[Settings.mongo_db_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"Ініціалізовано асинхронне підключення: {Settings.mongo_db_name}.{self.collection_name}")
        except Exception as e:
            logger.error(f"Помилка ініціалізації асинхронного підключення: {str(e)}")
            raise

    async def create_indexes(self) -> None:
        """Створює оптимальні індекси для колекції"""
        try:
            existing_indexes = []
            async for idx in self.collection.list_indexes():
                existing_indexes.append(idx)

            index_names = [idx["name"] for idx in existing_indexes]

            if self.collection_name == "source_videos":
                if not any("azure_link" in name for name in index_names):
                    await self.collection.create_index("azure_link", unique=True)
                    logger.info("Створено асинхронний унікальний індекс azure_link для source_videos")
                else:
                    logger.info("Асинхронний індекс azure_link для source_videos вже існує")

            elif self.collection_name == "video_clips":
                compound_exists = any("source_id_1_project_1_clip_id_1" in name for name in index_names)
                if not compound_exists:
                    await self.collection.create_index([
                        ("source_id", 1),
                        ("project", 1),
                        ("clip_id", 1)
                    ], unique=True)
                    logger.info("Створено асинхронний унікальний складний індекс для video_clips")
                else:
                    logger.info("Асинхронний унікальний складний індекс для video_clips вже існує")

                if not any("azure_link" in name for name in index_names):
                    await self.collection.create_index("azure_link", unique=False)
                    logger.info("Створено асинхронний індекс azure_link для швидкого пошуку")
                else:
                    logger.info("Асинхронний індекс azure_link для пошуку вже існує")

        except Exception as e:
            logger.error(f"Помилка при асинхронній роботі з індексами: {str(e)}")

    async def save_annotation(self, annotation: Union[Dict, BaseModel]) -> str:
        """Зберігає або оновлює анотацію з оптимізованою логікою"""
        try:
            data = self._prepare_annotation(annotation)
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            if self.collection_name == "source_videos":
                azure_link = data.get("azure_link")
                existing = await self.collection.find_one({"azure_link": azure_link})

                if existing:
                    data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                    await self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                    logger.info(f"Асинхронно оновлено соурс відео: {azure_link}")
                    return str(existing["_id"])
                else:
                    result = await self.collection.insert_one(data_without_id)
                    logger.info(f"Асинхронно створено нове соурс відео: {azure_link}")
                    return str(result.inserted_id)

            elif self.collection_name == "video_clips":
                source_id = data.get("source_id")
                project = data.get("project")
                clip_id = data.get("clip_id")

                source_id_obj = ObjectId(source_id) if isinstance(source_id, str) else source_id
                data_without_id["source_id"] = source_id_obj

                existing = await self.collection.find_one({
                    "source_id": source_id_obj,
                    "project": project,
                    "clip_id": clip_id
                })

                if existing:
                    data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                    await self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                    logger.info(f"Асинхронно оновлено кліп: {project} clip_id={clip_id}")
                    return str(existing["_id"])
                else:
                    result = await self.collection.insert_one(data_without_id)
                    logger.info(f"Асинхронно створено новий кліп: {project} clip_id={clip_id}")
                    return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка асинхронного збереження анотації: {str(e)}")
            raise

    async def get_annotation(self, identifier: str) -> Optional[Dict]:
        """Отримує анотацію за ідентифікатором"""
        try:
            if self.collection_name == "source_videos":
                doc = await self.collection.find_one({"azure_link": identifier})
            else:
                doc = await self.collection.find_one({"_id": ObjectId(identifier)})

            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання анотації: {str(e)}")
            raise

    async def get_clips_by_source_id(self, source_id: str) -> List[Dict]:
        """Отримує всі кліпи для вказаного соурс відео"""
        try:
            source_id_obj = ObjectId(source_id)
            cursor = self.collection.find({"source_id": source_id_obj})
            docs = await cursor.to_list(length=None)
            logger.info(f"Асинхронно знайдено {len(docs)} кліпів для source_id: {source_id}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання кліпів: {str(e)}")
            raise

    async def get_all_annotations(self, filter_query: Optional[Dict] = None) -> List[Dict]:
        """Отримує всі анотації з можливістю фільтрації"""
        try:
            query = filter_query or {}
            cursor = self.collection.find(query)
            docs = await cursor.to_list(length=None)
            logger.info(f"Асинхронно отримано {len(docs)} записів з колекції {self.collection_name}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання всіх анотацій: {str(e)}")
            raise

    async def delete_annotation(self, identifier: str) -> bool:
        """Видаляє анотацію за ідентифікатором"""
        try:
            if self.collection_name == "source_videos":
                result = await self.collection.delete_one({"azure_link": identifier})
            else:
                result = await self.collection.delete_one({"_id": ObjectId(identifier)})

            success = result.deleted_count > 0
            if success:
                logger.info(f"Асинхронно видалено запис: {identifier}")
            else:
                logger.warning(f"Асинхронно не знайдено запис для видалення: {identifier}")
            return success
        except Exception as e:
            logger.error(f"Помилка асинхронного видалення анотації: {str(e)}")
            raise

    def close(self) -> None:
        """Закриває з'єднання з MongoDB"""
        try:
            self.client.close()
            logger.info("Асинхронне з'єднання з MongoDB закрито")
        except Exception as e:
            logger.error(f"Помилка закриття асинхронного з'єднання: {str(e)}")


def create_repository(collection_name: str, async_mode: bool = False):
    """
    Створює репозиторій для роботи з MongoDB з оптимізованою логікою індексів

    Args:
        collection_name: Назва колекції
        async_mode: Використовувати асинхронну реалізацію

    Returns:
        Репозиторій для роботи з анотаціями відео
    """
    logger.info(f"Створення репозиторію: колекція={collection_name}, асинхронний={async_mode}")

    if async_mode:
        return AsyncVideoAnnotationRepository(collection_name=collection_name)
    else:
        return SyncVideoAnnotationRepository(collection_name=collection_name)