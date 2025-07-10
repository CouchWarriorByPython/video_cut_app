FROM python:3.13-slim

# Змінні середовища для Python
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TZ=Europe/Kiev

# Встановлення системних залежностей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    tzdata

# Налаштування часового поясу
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Створення робочої директорії
WORKDIR /app

# Копіювання requirements та встановлення Python залежностей
COPY requirements.txt .
RUN pip install -r requirements.txt

# Встановлення CVAT CLI
RUN pip install cvat-cli==2.3.0

# Копіювання коду проєкту
COPY . .

# Створення необхідних директорій
RUN mkdir -p temp logs temp/source_videos

# Команда за замовчуванням
CMD ["python", "backend/main.py"]