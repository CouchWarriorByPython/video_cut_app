# Import all tasks to ensure they are registered with Celery
from .video_processing import *
from .video_download_conversion import *
from .clip_processing import *
