from __future__ import annotations

from datetime import datetime, UTC
from mongoengine import Document, EmbeddedDocument, fields, ValidationError
from backend.models.shared import VideoStatus, MLProject, UserRole, CVATSettings


def _utc_now():
    """Helper function to get current UTC time"""
    return datetime.now(UTC)


class AzureFilePathDocument(EmbeddedDocument):
    """Azure file path structure for database documents"""
    account_name = fields.StringField(required=True, max_length=100)
    container_name = fields.StringField(required=True, max_length=100)
    blob_path = fields.StringField(required=True)

    @classmethod
    def from_pydantic(cls, azure_path) -> AzureFilePathDocument:
        """Create from Pydantic AzureFilePath model"""
        return cls(
            account_name=azure_path.account_name,
            container_name=azure_path.container_name,
            blob_path=azure_path.blob_path
        )

    def to_pydantic(self):
        """Convert to Pydantic AzureFilePath model"""
        from backend.models.shared import AzureFilePath
        return AzureFilePath(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_path=self.blob_path
        )


class CVATProjectSettingsDocument(Document):
    """CVAT project configuration with parameters"""
    project_name = fields.StringField(
        required=True,
        unique=True,
        choices=[project.value for project in MLProject]
    )
    project_id = fields.IntField(required=True, unique=True, min_value=1, max_value=1000)
    overlap = fields.IntField(required=True, min_value=0, max_value=100)
    segment_size = fields.IntField(required=True, min_value=50, max_value=2000)
    image_quality = fields.IntField(required=True, min_value=1, max_value=100)

    meta = {
        'collection': 'cvat_project_settings',
        'indexes': [
            'project_name',
            'project_id',
        ]
    }

    @classmethod
    def from_pydantic(cls, params: CVATSettings, project_name: str) -> CVATProjectSettingsDocument:
        """Create from Pydantic model"""
        return cls(
            project_name=project_name,
            project_id=params.project_id,
            overlap=params.overlap,
            segment_size=params.segment_size,
            image_quality=params.image_quality
        )

    def to_pydantic(self) -> CVATSettings:
        """Convert to Pydantic model"""
        return CVATSettings(
            project_name=self.project_name,
            project_id=self.project_id,
            overlap=self.overlap,
            segment_size=self.segment_size,
            image_quality=self.image_quality
        )


class VideoAnnotationDraftDocument(Document):
    """Draft annotation document - stores work-in-progress annotations"""
    source_video_id = fields.StringField(required=True)
    
    # Metadata fields
    skip_annotation = fields.BooleanField(default=False)
    where = fields.StringField(max_length=100)
    when = fields.StringField(max_length=8)  # YYYYMMDD format
    uav_type = fields.StringField(max_length=100)
    video_content = fields.StringField(max_length=100)
    is_urban = fields.BooleanField(default=False)
    has_osd = fields.BooleanField(default=False)
    is_analog = fields.BooleanField(default=False)
    night_video = fields.BooleanField(default=False)
    multiple_streams = fields.BooleanField(default=False)
    has_explosions = fields.BooleanField(default=False)
    
    # Clips data as JSON structure
    clips_data = fields.DictField(default=dict)  # Store project->clips mapping
    
    # Timestamps in UTC
    created_at_utc = fields.DateTimeField(default=_utc_now)
    updated_at_utc = fields.DateTimeField(default=_utc_now)

    meta = {
        'collection': 'video_annotation_drafts',
        'indexes': [
            'source_video_id',
            'created_at_utc',
            '-updated_at_utc',
        ]
    }

    def save(self, *args, **kwargs):
        """Update timestamp on save"""
        self.updated_at_utc = datetime.now(UTC)
        return super().save(*args, **kwargs)


class SourceVideoDocument(Document):
    """Source video document with optimized indexes for the workflow"""
    azure_file_path = fields.EmbeddedDocumentField(AzureFilePathDocument, required=True)
    status = fields.EnumField(VideoStatus, required=True, default=VideoStatus.DOWNLOADING)
    clips = fields.ListField(fields.StringField(), default=list)
    duration_sec = fields.IntField(min_value=0)
    size_MB = fields.FloatField(min_value=0)
    # Reference to draft annotation if exists
    annotation_draft_id = fields.StringField()
    # Skip annotation flag - duplicated from draft for convenience
    skip_annotation = fields.BooleanField(default=False)
    # Analog video flag - important metadata for skipped videos
    is_analog = fields.BooleanField(default=False)
    created_at_utc = fields.DateTimeField(default=_utc_now)
    updated_at_utc = fields.DateTimeField(default=_utc_now)

    meta = {
        'collection': 'source_videos',
        'indexes': [
            'azure_file_path.blob_path',
            'status',
            'created_at_utc',
            '-created_at_utc',
        ]
    }

    def save(self, *args, **kwargs):
        """Update timestamp and round size on save"""
        self.updated_at_utc = datetime.now(UTC)
        if self.size_MB is not None:
            self.size_MB = round(self.size_MB, 2)
        return super().save(*args, **kwargs)


class ClipVideoDocument(Document):
    """Clip video document based on the defined workflow"""
    source_video_id = fields.StringField(required=True)
    azure_file_path = fields.EmbeddedDocumentField(AzureFilePathDocument, required=True)
    extension = fields.StringField(required=True, max_length=10)

    # Metadata fields - validation handled by Pydantic models
    where = fields.StringField(max_length=100)
    when = fields.StringField(max_length=8)  # YYYYMMDD format validated in Pydantic
    uav_type = fields.StringField(max_length=100)
    video_content = fields.StringField(max_length=100)
    is_urban = fields.BooleanField(default=False)
    has_osd = fields.BooleanField(default=False)
    is_analog = fields.BooleanField(default=False)
    night_video = fields.BooleanField(default=False)
    multiple_streams = fields.BooleanField(default=False)
    has_explosions = fields.BooleanField(default=False)

    # CVAT integration fields
    ml_project = fields.EnumField(MLProject, required=True)
    cvat_project_id = fields.IntField(required=True, min_value=1, max_value=1000)
    cvat_task_params = fields.ReferenceField(CVATProjectSettingsDocument, required=True)
    cvat_task_id = fields.IntField()
    status = fields.StringField(required=True, default="not_annotated")

    # Video properties
    start_time_offset_sec = fields.IntField(required=True, min_value=0)
    duration_sec = fields.IntField(required=True, min_value=1)
    fps = fields.FloatField(min_value=0)
    resolution_width = fields.IntField(min_value=0)
    resolution_height = fields.IntField(min_value=0)
    size_MB = fields.FloatField(min_value=0)

    # Timestamps
    created_at_utc = fields.DateTimeField(default=_utc_now)
    updated_at_utc = fields.DateTimeField(default=_utc_now)

    meta = {
        'collection': 'clip_videos',
        'indexes': [
            'azure_file_path.blob_path',
            'source_video_id',
            'cvat_task_id',
            'ml_project',
            'status',
            'where',
            'when',
            'uav_type',
            'video_content',
            ('source_video_id', 'ml_project'),
            '-created_at_utc',
        ]
    }

    def clean(self):
        """Additional validation before save"""
        if self.start_time_offset_sec + self.duration_sec > 86400:  # 24 hours
            raise ValidationError("Clip cannot exceed 24 hours total duration")

    def save(self, *args, **kwargs):
        """Update timestamp, round size, and ensure extension has no dots on save"""
        self.updated_at_utc = datetime.now(UTC)
        if self.size_MB is not None:
            self.size_MB = round(self.size_MB, 2)
        # Ensure extension has no dots
        if self.extension and self.extension.startswith('.'):
            self.extension = self.extension[1:]
        return super().save(*args, **kwargs)


class UserDocument(Document):
    """User document for authentication and authorization"""
    email = fields.EmailField(required=True, unique=True)
    hashed_password = fields.StringField(required=True)
    role = fields.EnumField(UserRole, required=True)
    created_at_utc = fields.DateTimeField(default=_utc_now)
    updated_at_utc = fields.DateTimeField(default=_utc_now)
    is_active = fields.BooleanField(default=True)
    last_login_at_utc = fields.DateTimeField()

    meta = {
        'collection': 'users',
        'indexes': [
            'email',
            'is_active',
            ('email', 'is_active'),
        ]
    }

    def save(self, *args, **kwargs):
        """Update timestamp on save"""
        self.updated_at_utc = datetime.now(UTC)
        return super().save(*args, **kwargs)