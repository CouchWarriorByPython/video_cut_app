from backend.config.settings import Settings

broker_url = Settings.celery_broker_url
result_backend = Settings.celery_result_backend

task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

enable_utc = True
timezone = 'Europe/Kiev'

task_default_queue = 'default'

worker_send_task_events = True
task_send_sent_event = True

task_track_started = True
task_time_limit = 7200

task_routes = {
    'convert_video_for_web': {'queue': 'video_conversion'},
    'process_video_annotation': {'queue': 'video_processing'},
    'process_video_clip': {'queue': 'clip_processing'},
    'finalize_video_processing': {'queue': 'video_processing'},
}

task_annotations = {
    'convert_video_for_web': {'rate_limit': f'{Settings.max_conversion_workers}/m'},
}

worker_prefetch_multiplier = 1
task_acks_late = True
worker_max_tasks_per_child = 20

task_compression = 'gzip'
result_compression = 'gzip'

broker_connection_retry_on_startup = True
broker_connection_retry = True