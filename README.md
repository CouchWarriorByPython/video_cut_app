# 🎥 Video Annotation System

Система для завантаження відео з Azure Storage, розмітки фрагментів та автоматичної обробки через Celery.

---

## 🚀 Технології

* **Frontend**: Vanilla JS, HTML, CSS
* **Backend**: FastAPI, Celery, Redis
* **Database**: MongoDB
* **Storage**: Azure Blob Storage
* **Video Processing**: FFmpeg
* **Containerization**: Docker
* **Video Annotation**: CVAT

---

## 📋 Передумови

* Встановлений **Docker** та **Docker Compose**
* Файл `.env` (отримати у `dmytrobuz@pro-esupplies.com`)

---

## ⚡️ Швидкий старт

### 📟️ 1. Клонування репозиторію

```bash
git clone git@github.com:gtakontur/video-pre-annotator.git
cd video-annotation-system
```

### ⚙️ 2. Підготовка

* Додайте файл `.env` у корінь проєкту (поруч з `docker-compose-dev.yml`).

---

### ⛔️ 3. Зупинка попередніх контейнерів

```bash
docker compose -f docker-compose-dev.yml down
```

> 💡 Якщо потрібно повністю очистити середовище:

```bash
docker compose -f docker-compose-dev.yml down -v
```

---

### 🚀 4. Запуск сервісів

* З перебудовою (для першого запуску або після `git pull`):

  ```bash
  docker compose -f docker-compose-dev.yml up --build
  ```

* Звичайний запуск:

  ```bash
  docker compose -f docker-compose-dev.yml up
  ```

> 🔁 Щоб запустити у фоні, додай `-d`

```bash
docker compose -f docker-compose-dev.yml up -d
```

---

## 🌐 Доступні сервіси

| Сервіс           | URL                                                      | Опис                           |
| ---------------- | -------------------------------------------------------- | ------------------------------ |
| Веб-інтерфейс    | [http://localhost:8000](http://localhost:8000)           | Завантаження та розмітка відео |
| API документація | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI від FastAPI         |
| Mongo Express    | [http://localhost:8081](http://localhost:8081)           | Веб-інтерфейс MongoDB          |
| Flower           | [http://localhost:5555](http://localhost:5555)           | Монітор Celery задач           |

---

## 📁 Структура проєкту

```
├── backend/
│   ├── api/               # FastAPI endpoints
│   ├── background_tasks/  # Celery задачі
│   ├── config/            # Налаштування
│   ├── database/          # MongoDB репозиторії
│   ├── models/            # Pydantic моделі
│   ├── services/          # Бізнес-логіка
│   └── utils/             # Допоміжні функції
├── front/                 # Фронтенд
├── docker/                # Docker конфігурація
├── temp/                  # Тимчасові файли (auto)
└── logs/                  # Логи (auto)
```

---

## 🌟 Основний функціонал

### 📅 1. Завантаження відео

* Реєстрація відео з Azure Blob URL
* Збереження на локальний сервер

### ✂️ 2. Розмітка фрагментів

* Точки початку/кінця кліпів
* Підтримка проєктів: Motion Detection, Tracking, Mil Hardware, Re-ID
* Додавання метаданих: тип дрону, відеоконтент тощо

### ⚙️ 3. Celery обробка

* Нарізка кліпів за вставленими точками
* Завантаження кліпів назад в Azure
* Створення задач CVAT для анотації

---

## 🔧 Управління системою

### 🔚 Перегляд логів

```bash
# Усі сервіси
docker compose logs

# Окремі сервіси
docker compose logs app
docker compose logs celery-worker
```

---

## 📊 Моніторинг

* **Flower** — Celery dashboard
* **logs/** — логи сервісів
* **Mongo Express** — графічний інтерфейс MongoDB

---

## ⚠️ Важливо

* Файл `.env` є обов'язковим для працездатності проєкту