FROM python:3.13-slim

# Встановлення системних залежностей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

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

# Експозиція порту
EXPOSE 8000

# Команда за замовчуванням
CMD ["python", "-m", "uvicorn", "backend.main:app"]