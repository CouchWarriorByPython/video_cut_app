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

# Video Cut Application

## Опис проекту

Video Cut Application - це веб-додаток для завантаження, обробки та анотування відео з Azure Storage. Система підтримує асинхронну обробку відео, автоматичну конвертацію форматів і зручний інтерфейс для роботи з відео.

## Основні функції

### 📥 Завантаження відео
- **Одиночне завантаження**: Підтримка одного Azure URL
- **Множинне завантаження**: Обробка декількох URL одночасно  
- **Завантаження папки**: Автоматичне завантаження всіх відео з Azure папки
- **Інтелектуальна перевірка**: Автоматична перевірка локального існування файлів

### 🔄 Покращений флоу обробки відео

#### Стани відео:
1. **Готове локально** ✅ - відео є в БД і локально, готове для анотації
2. **Перезавантаження** 🔄 - відео є в БД але відсутнє локально, перезавантажується
3. **Нове завантаження** ⬇️ - нове відео додається в чергу завантаження
4. **Помилка** ❌ - проблеми з обробкою або валідацією

#### Логіка обробки:
```
Для кожного відео:
├── Валідація Azure URL
├── Перевірка існування в БД
│   ├── Є в БД?
│   │   ├── Є локально? → Готове ✅
│   │   └── Немає локально? → Перезавантаження 🔄
│   └── Немає в БД? → Нове завантаження ⬇️
```

### 🎨 Покращений користувацький інтерфейс

#### Модальні вікна з детальною інформацією:
- **Адаптивний дизайн** для всіх розмірів екранів
- **Категоризація результатів** за типами (готові, завантажуються, помилки)
- **Кольорове кодування** для швидкого розпізнавання станів
- **Довгі назви файлів** корректно відображаються з переносом

#### Прогрес-бари:
- **Індивідуальні прогрес-бари** для кожного відео
- **Пакетний прогрес** для множинних завантажень
- **Реальний час відстеження** статусу завдань
- **Автоматичне очищення** завершених завдань

### 📊 Етапи обробки відео:

1. **Queued** (В черзі) - 0%
2. **Downloading** (Завантаження) - 5-50%
3. **Analyzing** (Аналіз) - 50-60%
4. **Converting** (Конвертація) - 60-95%
5. **Finalizing** (Завершення) - 95-100%
6. **Completed** (Готово) - 100%

## Технічна архітектура

### Backend:
- **FastAPI** - REST API
- **MongoDB** - база даних
- **Celery** - асинхронні завдання
- **Azure SDK** - робота з Azure Storage
- **FFmpeg** - обробка відео

### Frontend:
- **Vanilla JavaScript** - без фреймворків
- **CSS Grid/Flexbox** - адаптивна верстка
- **WebSocket** - реальний час оновлення (опційно)

### Background Tasks:
- **Завантаження з Azure** з відстеженням прогресу
- **Автоматична конвертація** в web-сумісні формати
- **Обробка помилок** та повтори

## Покращення UI/UX

### ✨ Нові функції:

#### 1. Інформаційні модальні вікна
```javascript
// Структура інформації:
{
  "ready": ["готові відео"],
  "downloading": ["відео що завантажуються"], 
  "errors": ["помилки обробки"]
}
```

#### 2. Адаптивний дизайн
- **Desktop**: повноцінний інтерфейс з боковими панелями
- **Tablet**: оптимізована компоновка
- **Mobile**: вертикальний стек елементів

#### 3. Покращена обробка помилок
- **Детальні повідомлення** про помилки
- **Контекстні підказки** для вирішення проблем
- **Автоматичні повтори** для тимчасових помилок

#### 4. Інтелектуальні повідомлення
- **Категоризація за типами** (успіх, інформація, попередження, помилка)
- **Іконки та кольори** для швидкого розпізнавання
- **Довгі назви** з коректним переносом

## Використання

### Завантаження одного відео:
1. Вставте Azure URL відео
2. Натисніть "Зареєструвати відео"
3. Відстежуйте прогрес у реальному часі

### Завантаження декількох відео:
1. Вставте URLs через кому
2. Система обробить кожне відео
3. Побачите детальну інформацію в модальному вікні

### Завантаження папки:
1. Вставте URL папки в Azure
2. Увімкніть опцію "Завантажити всі відео з папки"  
3. Система знайде та обробить всі відео файли

## Конфігурація

### Змінні середовища:
```env
MONGO_URI=mongodb://localhost:27017/video_cut_app
AZURE_STORAGE_CONNECTION_STRING=your_connection_string
CELERY_BROKER_URL=redis://localhost:6379
SKIP_CONVERSION_FOR_COMPATIBLE=true
VIDEO_CONVERSION_PRESET=medium
VIDEO_CONVERSION_CRF=23
```

### Підтримувані формати:
- **Вхідні**: MP4, AVI, MOV, MKV
- **Вихідні**: MP4 (H.264 + AAC)

## Запуск

### Розробка:
```bash
# Backend
cd backend
python -m uvicorn main:app --reload

# Frontend (статичні файли обслуговуються FastAPI)
# Celery worker
celery -A backend.background_tasks.app worker --loglevel=info
```

### Продакшн:
```bash
docker-compose -f docker-compose-prod.yml up -d
```

## Docker деплоймент

### Розробка

```bash
# Запуск всіх сервісів
docker-compose -f docker-compose-dev.yml up --build

# Перегляд логів
docker-compose -f docker-compose-dev.yml logs -f

# Зупинка сервісів
docker-compose -f docker-compose-dev.yml down
```

### Продакшн

```bash
# Запуск всіх сервісів у фоні
docker-compose -f docker-compose-prod.yml up --build -d

# Перегляд логів додатку
docker-compose -f docker-compose-prod.yml logs -f app

# Зупинка сервісів
docker-compose -f docker-compose-prod.yml down
```

### Docker сервіси

Система включає наступні Docker контейнери:
- **app**: Основний FastAPI додаток
- **celery-general**: Обробка загальних задач (відео/кліп обробка)
- **celery-conversion**: Конвертація відео
- **celery-maintenance**: Системне обслуговування
- **celery-beat**: Планувальник періодичних задач (автоматичне очищення)
- **redis**: In-memory сховище для блокувань та кешування
- **mongodb**: Основна база даних
- **nginx**: Веб-сервер та reverse proxy
- **flower**: Моніторинг Celery (доступний на http://localhost:5556)

### Моніторинг Docker

```bash
# Перевірка статусу контейнерів
docker-compose -f docker-compose-dev.yml ps

# Перегляд логів конкретного сервісу
docker-compose -f docker-compose-dev.yml logs -f celery-beat
docker-compose -f docker-compose-dev.yml logs -f celery-maintenance

# Виконання команд в контейнерах
docker-compose -f docker-compose-dev.yml exec app bash
docker-compose -f docker-compose-dev.yml exec redis redis-cli INFO

# Перезапуск конкретних сервісів
docker-compose -f docker-compose-dev.yml restart celery-beat
```

## Моніторинг та логи

### Логи зберігаються в:
- `logs/main.log` - основні події
- `logs/services.log` - сервіси та обробка
- `logs/tasks.log` - background завдання

### Метрики:
- Кількість активних завантажень
- Середній час обробки відео
- Статистика помилок

## Розробка

### Структура проекту:
```
video_cut_app/
├── backend/           # Python FastAPI backend
├── frontend/          # HTML/CSS/JS frontend  
├── docker/           # Docker конфігурації
├── logs/             # Логи системи
└── nginx/            # Nginx конфігурації
```

### Внесення змін:
1. **Backend**: модифікуйте сервіси в `backend/services/`
2. **Frontend**: редагуйте файли в `frontend/`
3. **Стилі**: оновлюйте CSS в `frontend/css/`
4. **API**: додавайте endpoints в `backend/api/endpoints/`

## Покращення які були реалізовані

### 🎯 Основні покращення:

1. **Інтелектуальна перевірка файлів**:
   - Перевірка існування в БД
   - Перевірка локального існування  
   - Автоматичне перезавантаження відсутніх файлів

2. **Покращений UI для інформації**:
   - Модальні вікна замість простих alert
   - Структурована інформація за категоріями
   - Адаптивний дизайн для всіх пристроїв

3. **Кращі повідомлення**:
   - Детальні статуси для кожного відео
   - Кольорове кодування станів
   - Коректне відображення довгих назв

4. **Пакетна обробка**:
   - Прогрес-бари для batch операцій
   - Паралельна обробка відео
   - Оптимізована продуктивність

5. **Покращена обробка помилок**:
   - Детальні повідомлення про помилки
   - Контекстні підказки
   - Graceful degradation

### 📈 Результат покращень:

- ✅ **Краща інформативність** - користувач завжди знає що відбувається
- ✅ **Покращений UX** - зручний інтерфейс для всіх сценаріїв
- ✅ **Надійність** - інтелектуальна обробка різних станів файлів
- ✅ **Масштабованість** - ефективна обробка великої кількості файлів
- ✅ **Адаптивність** - працює на всіх пристроях

## Підтримка

Для питань та проблем створюйте issues в репозиторії або звертайтесь до команди розробки.

## Діагностика та усунення проблем

### Проблеми з авторизацією після тривалої роботи

Якщо через день-півтора система перестає працювати з авторизацією, використовуйте наступні кроки:

#### 1. Діагностика системи
1. Увійдіть в адмін панель (http://localhost:8888/admin)
2. Перейдіть на вкладку "Діагностика" 
3. Натисніть "Перевірити стан"
4. Перевірте стан Redis та MongoDB

#### 2. Docker-специфічна діагностика
```bash
# Перевірка всіх контейнерів
docker-compose -f docker-compose-dev.yml ps

# Перевірка роботи Celery Beat (має показувати periodic_system_cleanup)
docker-compose -f docker-compose-dev.yml logs celery-beat

# Перевірка Redis здоров'я
docker-compose -f docker-compose-dev.yml exec redis redis-cli PING

# Кількість ключів у Redis
docker-compose -f docker-compose-dev.yml exec redis redis-cli DBSIZE

# Перегляд блокувань
docker-compose -f docker-compose-dev.yml exec redis redis-cli KEYS "video_lock:*"
```

#### 3. Очищення застарілих блокувань
```bash
# В адмін панелі натисніть "Очистити блокування"
# Або виконайте API запит:
curl -X POST http://localhost:8888/admin/cleanup-locks \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 4. Примусове очищення (екстрений випадок)
```bash
# УВАГА: Видаляє ВСІ блокування
curl -X POST http://localhost:8888/admin/force-cleanup-locks \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 5. Перезапуск сервісів
```bash
# Перезапуск конкретних сервісів
docker-compose -f docker-compose-dev.yml restart app
docker-compose -f docker-compose-dev.yml restart celery-beat  
docker-compose -f docker-compose-dev.yml restart redis

# Перезапуск всіх сервісів
docker-compose -f docker-compose-dev.yml restart
```

### Автоматичне очищення

Система автоматично очищає застарілі дані кожну годину через Celery Beat.

**В Docker**: Контейнер `celery-beat` керує автоматичним очищенням. Перевірте його логи:
```bash
docker-compose -f docker-compose-dev.yml logs -f celery-beat
```

#### Моніторинг URL (коли система запущена):
- **Адмін панель**: http://localhost:8888/admin
- **Celery Flower**: http://localhost:5556
- **MongoDB Express**: http://localhost:8082

#### Ручний запуск Celery Beat (без Docker):
```bash
cd backend && celery -A backend.background_tasks.app beat --loglevel=info
```

### Логування

Детальне логування знаходиться в:
- `logs/services.log` - основні сервіси
- `logs/api.log` - API запити
- `logs/middleware.log` - авторизація
- `logs/tasks.log` - background задачі

### Моніторинг стану

#### Ендпоінти для моніторингу:
- `GET /admin/system-health` - стан системи
- `POST /admin/cleanup-locks` - очищення блокувань
- `POST /admin/force-cleanup-locks` - примусове очищення