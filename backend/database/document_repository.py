from typing import TypeVar, Generic, List, Optional, Dict, Any, Type
from mongoengine import Document, NotUniqueError
from backend.utils.logger import get_logger

T = TypeVar('T', bound=Document)
logger = get_logger(__name__, "repository.log")


class BaseDocumentRepository(Generic[T]):
    """Base repository for MongoEngine documents"""

    def __init__(self, document_class: Type[T]):
        self.document_class = document_class
        self.collection_name = document_class._meta['collection']

    def create(self, **kwargs) -> T:
        """Create new document"""
        try:
            document = self.document_class(**kwargs)
            document.save()
            logger.debug(f"Created document in {self.collection_name}: {document.id}")
            return document
        except NotUniqueError as e:
            logger.error(f"Unique constraint violation in {self.collection_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating document in {self.collection_name}: {str(e)}")
            raise

    def get_by_id(self, doc_id: str) -> Optional[T]:
        """Get document by ID"""
        try:
            return self.document_class.objects(id=doc_id).first()
        except Exception as e:
            logger.error(f"Error finding document by ID {doc_id}: {str(e)}")
            raise

    def get_by_field(self, field: str, value: Any) -> Optional[T]:
        """Get document by field"""
        try:
            # Convert dot notation to MongoEngine double underscore notation for embedded documents
            mongo_field = field.replace('.', '__')
            query_dict = {mongo_field: value}
            return self.document_class.objects(**query_dict).first()
        except Exception as e:
            logger.error(f"Error finding document by {field}={value}: {str(e)}")
            raise

    def get_all(self, filter_dict: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[T]:
        """Get all documents with optional filtering"""
        try:
            # Convert dot notation in filter dict
            if filter_dict:
                mongo_filter = {}
                for key, value in filter_dict.items():
                    mongo_key = key.replace('.', '__')
                    mongo_filter[mongo_key] = value
                query = self.document_class.objects(**mongo_filter)
            else:
                query = self.document_class.objects()

            if limit:
                query = query.limit(limit)
            return list(query)
        except Exception as e:
            logger.error(f"Error getting documents from {self.collection_name}: {str(e)}")
            raise

    def update_by_id(self, doc_id: str, update_data: Dict[str, Any]) -> bool:
        """Update document by ID"""
        try:
            document = self.get_by_id(doc_id)
            if not document:
                return False

            for key, value in update_data.items():
                setattr(document, key, value)

            document.save()
            logger.debug(f"Updated document in {self.collection_name}: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating document {doc_id}: {str(e)}")
            raise

    def update_by_field(self, field: str, value: Any, update_data: Dict[str, Any]) -> bool:
        """Update document by field"""
        try:
            document = self.get_by_field(field, value)
            if not document:
                return False

            for key, update_value in update_data.items():
                setattr(document, key, update_value)

            document.save()
            logger.debug(f"Updated document in {self.collection_name} by {field}={value}")
            return True
        except Exception as e:
            logger.error(f"Error updating document by {field}={value}: {str(e)}")
            raise

    def delete_by_id(self, doc_id: str) -> bool:
        """Delete document by ID"""
        try:
            document = self.get_by_id(doc_id)
            if not document:
                return False

            document.delete()
            logger.info(f"Deleted document from {self.collection_name}: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {str(e)}")
            raise

    def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Count documents"""
        try:
            if filter_dict:
                mongo_filter = {}
                for key, value in filter_dict.items():
                    mongo_key = key.replace('.', '__')
                    mongo_filter[mongo_key] = value
                return self.document_class.objects(**mongo_filter).count()
            else:
                return self.document_class.objects().count()
        except Exception as e:
            logger.error(f"Error counting documents in {self.collection_name}: {str(e)}")
            raise

    def exists(self, **kwargs) -> bool:
        """Check if document exists"""
        try:
            # Convert dot notation in kwargs
            mongo_kwargs = {}
            for key, value in kwargs.items():
                mongo_key = key.replace('.', '__')
                mongo_kwargs[mongo_key] = value
            return self.document_class.objects(**mongo_kwargs).first() is not None
        except Exception as e:
            logger.error(f"Error checking existence in {self.collection_name}: {str(e)}")
            raise