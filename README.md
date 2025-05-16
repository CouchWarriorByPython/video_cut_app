# 🎬 Video Pre-Annotator

**Video Pre-Annotator** — це веб-додаток для швидкої розмітки відео: встановлення фрагментів, додавання метаданих, і підготовка кліпів до подальшої обробки або навчання моделей.

## 🧩 Основний функціонал

- Завантаження відео через інтерфейс drag & drop
- Інтерактивна відео-таймлінія для встановлення фрагментів
- Вибір проєктів (Motion Detection, Tracking, Re-ID тощо)
- Додавання метаданих (тип дрона, контент, додаткові ознаки)
- Експорт результатів у JSON
- Підготовка до нарізки на кліпи
- Планується: автонарізка, автотести, Azure-деплой

## 🛠️ Технології

- **Frontend**: [Vue.js](https://vuejs.org/)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/)
- **БД**: [MongoDB](https://www.mongodb.com/)
- **Контейнери**: Docker, Docker Compose
- **Інфраструктура**: Azure (деплой)
- **Тестування**: Pytest

## 🚀 Швидкий старт

```bash
git clone https://github.com/your-username/video-pre-annotator.git
cd video-pre-annotator
docker-compose up --build
```

# Бекенд архітектура (планова)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── security.py
│   │   └── logging.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   ├── auth.py
│   │       │   ├── dashboard.py
│   │       │   ├── annotation.py
│   │       │   └── docs.py
│   │       └── router.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── video.py
│   │   └── docs.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── video.py
│   │   └── docs.py
│   ├── crud/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── video.py
│   │   └── docs.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── video_service.py
│   │   ├── annotation_service.py
│   │   ├── azure_service.py
│   │   └── lock_service.py
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   └── tasks.py
│   └── utils/
│       ├── __init__.py
│       ├── video_utils.py
│       └── azure_utils.py
├── static/
│   └── docs/
│       └── images/
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_api/
    │   ├── __init__.py
    │   ├── test_auth.py
    │   ├── test_dashboard.py
    │   └── test_annotation.py
    └── test_services/
        ├── __init__.py
        ├── test_video_service.py
        └── test_annotation_service.py
```

# Фронтенд архітектура (планова)

```
frontend/
├── public/
│   ├── favicon.ico
│   └── index.html
├── src/
│   ├── main.js
│   ├── App.vue
│   ├── assets/
│   │   ├── logo.svg
│   │   ├── styles/
│   │   │   ├── main.scss
│   │   │   ├── variables.scss
│   │   │   └── components.scss
│   │   └── icons/
│   ├── components/
│   │   ├── common/
│   │   │   ├── BaseButton.vue
│   │   │   ├── BaseInput.vue
│   │   │   ├── BaseAlert.vue
│   │   │   ├── BaseModal.vue
│   │   │   └── LoadingSpinner.vue
│   │   ├── layout/
│   │   │   ├── TheHeader.vue
│   │   │   ├── TheSidebar.vue
│   │   │   └── TheFooter.vue
│   │   ├── auth/
│   │   │   ├── LoginForm.vue
│   │   │   └── ForgotPasswordForm.vue
│   │   ├── dashboard/
│   │   │   ├── VideoUploader.vue
│   │   │   ├── VideoList.vue
│   │   │   └── VideoCard.vue
│   │   ├── annotation/
│   │   │   ├── VideoPlayer.vue
│   │   │   ├── TimelineEditor.vue
│   │   │   ├── AnnotationForm.vue
│   │   │   └── TagSelector.vue
│   │   └── docs/
│   │       ├── ParameterExplainer.vue
│   │       └── ImageViewer.vue
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── DashboardView.vue
│   │   ├── AnnotationView.vue
│   │   ├── DocsView.vue
│   │   └── NotFoundView.vue
│   ├── router/
│   │   ├── index.js
│   │   └── guards.js
│   ├── stores/
│   │   ├── auth.js
│   │   ├── videos.js
│   │   ├── annotations.js
│   │   └── docs.js
│   ├── services/
│   │   ├── api.js
│   │   ├── authService.js
│   │   ├── videoService.js
│   │   ├── annotationService.js
│   │   └── docsService.js
│   ├── utils/
│   │   ├── formatters.js
│   │   ├── validators.js
│   │   └── videoUtils.js
│   └── constants/
│       ├── routes.js
│       ├── videoStatuses.js
│       └── roles.js
├── .env
├── .env.development
├── .env.production
├── package.json
├── vite.config.js
└── README.md
```