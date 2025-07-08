from backend.config.settings import get_settings

settings = get_settings()

broker_url = settings.celery_broker_url
result_backend = settings.celery_result_backend

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
    'download_and_convert_video': {'queue': 'video_conversion'},
    'process_video_annotation': {'queue': 'video_processing'},
    'process_video_clip': {'queue': 'clip_processing'},
    'finalize_video_processing': {'queue': 'video_processing'},
    'periodic_system_cleanup': {'queue': 'maintenance'},
}

# Періодичні задачі
beat_schedule = {
    'system-cleanup': {
        'task': 'periodic_system_cleanup',
        'schedule': 3600.0,  # Кожну годину
        'options': {'queue': 'maintenance'}
    },
}

# Видаляємо rate_limit для швидшої обробки
task_annotations = {
    'download_and_convert_video': {'rate_limit': None},
    'periodic_system_cleanup': {'rate_limit': '1/h'},  # Не більше 1 разу на годину
}

# Оптимізація для швидкої обробки черги
worker_prefetch_multiplier = 4  # Збільшуємо з 1 до 4
task_acks_late = True
worker_max_tasks_per_child = 50  # Збільшуємо з 20 до 50

task_compression = 'gzip'
result_compression = 'gzip'

broker_connection_retry_on_startup = True
broker_connection_retry = True

result_expires = 86400
task_ignore_result = False
task_store_eager_result = True

# Додаємо для швидшої обробки
task_soft_time_limit = 3600
task_reject_on_worker_lost = True
