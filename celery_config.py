from configs import Settings

# Налаштування брокера
broker_url = Settings.celery_broker_url
result_backend = Settings.celery_result_backend

# Серіалізація
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Часові зони
enable_utc = True
timezone = 'Europe/Kiev'

# Налаштування черг
task_default_queue = 'default'

# Налаштування для моніторингу
worker_send_task_events = True
task_send_sent_event = True

# Додаткові налаштування
task_track_started = True
task_time_limit = 3600  # 1 година таймаут