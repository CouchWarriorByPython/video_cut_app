# Video Annotation System

Система для завантаження відео з Azure Storage, розмітки фрагментів та автоматичної обробки через Celery.

## 🚀 Технології

- **Frontend**: Vanilla JS, HTML, CSS
- **Backend**: FastAPI, Celery, Redis
- **Database**: MongoDB
- **Storage**: Azure Blob Storage
- **Video Processing**: FFmpeg
- **Container**: Docker
- **Video annotation**: CVAT

## 📋 Передумови

- Docker і Docker Compose
- `.env` файл (отримати у dmytrobuz@pro-esupplies.com)

## ⚡ Швидкий старт

```bash
# Клонування репозиторію
git clone git@github.com:gtakontur/video-pre-annotator.git
cd video-annotation-system

# Розмістити .env файл в корені проєкту

# Запуск всіх сервісів вперше
docker compose up --build

# Запуск всіх сервісів якщо вже запускали до цього
docker compose up
```

## 🌐 Доступні сервіси

| Сервіс | URL | Опис |
|--------|-----|------|
| **Веб-інтерфейс** | http://localhost:8000 | Головна сторінка завантаження відео |
| **API документація** | http://localhost:8000/docs | FastAPI Swagger UI |
| **Mongo Express** | http://localhost:8081 | Веб-інтерфейс MongoDB |
| **Flower** | http://localhost:5555 | Моніторинг Celery задач |

## 📁 Структура проєкту

```
├── backend/
│   ├── api/               # FastAPI endpoints
│   ├── background_tasks/  # Celery задачі
│   ├── config/           # Налаштування
│   ├── database/         # MongoDB репозиторії
│   ├── models/           # Pydantic моделі
│   ├── services/         # Бізнес-логіка
│   └── utils/            # Допоміжні функції
├── front/                # Frontend файли
├── docker/               # Docker конфігурація
├── temp/                 # Тимчасові файли (створюється автоматично)
└── logs/                 # Логи (створюється автоматично)
```

## 🎯 Основний функціонал

1. **Завантаження відео**
   - Реєстрація відео за Azure Blob URL
   - Автоматичне завантаження на локальний сервер

2. **Розмітка відео**
   - Встановлення часових міток для фрагментів
   - Підтримка кількох проєктів: Motion Detection, Tracking, Mil Hardware, Re-ID
   - Додавання метаданих (тип дрону, контент, параметри)

3. **Обробка через Celery**
   - Автоматична нарізка відео на фрагменти
   - Завантаження кліпів назад в Azure Storage
   - Створення задач в CVAT для анотування

## 🔧 Управління системою

### Перегляд логів
```bash
# Всі сервіси
docker compose logs

# Конкретний сервіс
docker compose logs app
docker compose logs celery-worker
```

### Зупинка сервісів
```bash
docker compose down -v
```

## 📊 Моніторинг

- **Flower** - відстеження виконання Celery задач в реальному часі
- **Logs** - детальні логи в папці `logs/`
- **MongoDB** - перегляд даних через Mongo Express

## ⚠️ Важливо

- Переконайтеся, що додали .env файл в корень проєкту