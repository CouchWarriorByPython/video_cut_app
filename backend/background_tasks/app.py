from celery import Celery

app = Celery('video_annotation_tasks')
app.config_from_object('backend.background_tasks.config')

app.autodiscover_tasks([
    'backend.background_tasks.tasks.video_processing',
    'backend.background_tasks.tasks.clip_processing',
    'backend.background_tasks.tasks.video_conversion'
])