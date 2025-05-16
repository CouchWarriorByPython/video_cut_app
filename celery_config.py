from typing import List

# Налаштування брокера
broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"

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