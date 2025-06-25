from celery import Celery
from celery.signals import worker_init
from backend.database.connection import DatabaseConnection
from backend.utils.logger import get_logger

logger = get_logger(__name__, "celery.log")

app = Celery('video_annotation_tasks')
app.config_from_object('backend.background_tasks.config')

@worker_init.connect
def configure_worker(sender=None, **kwargs):
    """Initialize worker with database connection"""
    try:
        DatabaseConnection.connect()
        logger.info("Worker initialized with database connection")
    except Exception as e:
        logger.error(f"Failed to initialize worker: {str(e)}")
        raise

app.autodiscover_tasks([
    'backend.background_tasks.tasks.video_download_conversion',
    'backend.background_tasks.tasks.video_processing',
    'backend.background_tasks.tasks.clip_processing'
])