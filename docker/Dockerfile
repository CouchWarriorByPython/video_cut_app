FROM python:3.13-slim

# Змінні середовища для Python
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TZ=Europe/Kiev
#    PIP_NO_CACHE_DIR=1 \
# Встановлення системних залежностей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Налаштування часового поясу
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Створення робочої директорії
WORKDIR /app

# Копіювання requirements та встановлення Python залежностей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Встановлення CVAT CLI
RUN pip install cvat-cli==2.3.0

# Копіювання коду проєкту
COPY . .

# Створення необхідних директорій
RUN mkdir -p temp logs temp/source_videos

# Команда за замовчуванням - запуск через main.py щоб використати Settings
CMD ["python", "backend/main.py"]