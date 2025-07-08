from backend.database.document_repository import BaseDocumentRepository
from backend.models.documents import (
    SourceVideoDocument, ClipVideoDocument,
    UserDocument, CVATProjectSettingsDocument,
    VideoAnnotationDraftDocument
)


def create_source_video_repository() -> BaseDocumentRepository[SourceVideoDocument]:
    """Create source video repository"""
    return BaseDocumentRepository(SourceVideoDocument)


def create_clip_video_repository() -> BaseDocumentRepository[ClipVideoDocument]:
    """Create clip video repository"""
    return BaseDocumentRepository(ClipVideoDocument)


def create_user_repository() -> BaseDocumentRepository[UserDocument]:
    """Create user repository"""
    return BaseDocumentRepository(UserDocument)


def create_cvat_settings_repository() -> BaseDocumentRepository[CVATProjectSettingsDocument]:
    """Create CVAT settings repository"""
    return BaseDocumentRepository(CVATProjectSettingsDocument)


def create_annotation_draft_repository() -> BaseDocumentRepository[VideoAnnotationDraftDocument]:
    """Create annotation draft repository"""
    return BaseDocumentRepository(VideoAnnotationDraftDocument)