from typing import Dict, List, Optional, Union
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

from backend.utils.logger import get_logger

logger = get_logger(__name__, "database.log")


class AnnotationBase:
    """Базовий клас для роботи з анотаціями відео"""

    def __init__(self, collection_name: str) -> None:
        """Ініціалізує клас з вказаною колекцією"""
        self.collection_name = collection_name
        logger.debug(f"Ініціалізація репозиторію для колекції: {collection_name}")

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