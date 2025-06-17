// =================== КОНСТАНТИ ===================
const CONFIG = {
    API_BASE_URL: '',
    SUPPORTED_VIDEO_FORMATS: ['.mp4', '.avi', '.mov', '.mkv'],
    MIN_CLIP_DURATION: 1,
    DATE_FORMAT: 'РРРРММДД',
    LOCATION_PATTERN: /^[A-Za-z\s\-_]+$/,
    DATE_PATTERN: /^\d{8}$/,

    ROLES: {
        ANNOTATOR: 'annotator',
        ADMIN: 'admin',
        SUPER_ADMIN: 'super_admin'
    },

    PAGES: {
        LOGIN: '/login',
        UPLOAD: '/',
        ANNOTATOR: '/annotator',
        FAQ: '/faq',
        ADMIN: '/admin'
    }
};

// =================== УТІЛІТИ ===================
const Utils = {
    /**
     * Форматування часу з секунд у HH:MM:SS
     */
    formatTime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    },

    /**
     * Конвертація часу HH:MM:SS в секунди
     */
    timeToSeconds(timeString) {
        const parts = timeString.split(':');
        return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
    },

    /**
     * Екранування HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Форматування дати
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('uk-UA', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },

    /**
     * Генерація унікального ID
     */
    generateId() {
        return 'id_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    },

    /**
     * Дебаунс функція
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// =================== ВАЛІДАЦІЯ ===================
const Validators = {
    /**
     * Валідація Azure URL
     */
    isValidAzureUrl(url) {
        try {
            const urlObj = new URL(url);
            return urlObj.hostname.includes('.blob.core.windows.net') &&
                   urlObj.pathname.length > 1 &&
                   CONFIG.SUPPORTED_VIDEO_FORMATS.some(ext =>
                       url.toLowerCase().endsWith(ext)
                   );
        } catch {
            return false;
        }
    },

    /**
     * Валідація email
     */
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    /**
     * Валідація локації
     */
    isValidLocation(location) {
        return !location || CONFIG.LOCATION_PATTERN.test(location);
    },

    /**
     * Валідація дати
     */
    isValidDate(date) {
        return !date || CONFIG.DATE_PATTERN.test(date);
    },

    /**
     * Валідація пароля
     */
    isValidPassword(password) {
        return password && password.length >= 8;
    },

    /**
     * Валідація тривалості кліпу
     */
    isValidClipDuration(startTime, endTime) {
        const start = Utils.timeToSeconds(startTime);
        const end = Utils.timeToSeconds(endTime);
        return (end - start) >= CONFIG.MIN_CLIP_DURATION;
    }
};

// =================== UI УТІЛІТИ ===================
const UI = {
    /**
     * Показати лоадер
     */
    showLoader(message = 'Завантаження...') {
        const loader = document.createElement('div');
        loader.id = 'app-loader';
        loader.className = 'loading-overlay';
        loader.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <p>${Utils.escapeHtml(message)}</p>
            </div>
        `;
        document.body.appendChild(loader);
    },

    /**
     * Приховати лоадер
     */
    hideLoader() {
        const loader = document.getElementById('app-loader');
        if (loader) {
            loader.remove();
        }
    },

    /**
     * Встановити стан кнопки
     */
    setButtonState(button, loading = false, text = null) {
        if (!button) return;

        button.disabled = loading;
        if (text) {
            button.textContent = loading ? '' : text;
        }

        if (loading) {
            button.classList.add('loading');
        } else {
            button.classList.remove('loading');
        }
    },

    /**
     * Встановити стан валідації поля
     */
    setFieldValidation(field, isValid, message = '') {
        if (!field) return;

        field.style.borderColor = isValid ? '' : '#e74c3c';

        let errorElement = field.parentNode.querySelector('.field-error');
        if (!isValid && message) {
            if (!errorElement) {
                errorElement = document.createElement('div');
                errorElement.className = 'field-error';
                field.parentNode.appendChild(errorElement);
            }
            errorElement.textContent = message;
        } else if (errorElement) {
            errorElement.remove();
        }
    },

    /**
     * Очистити всі помилки валідації у формі
     */
    clearFormErrors(form) {
        const errors = form.querySelectorAll('.field-error');
        errors.forEach(error => error.remove());

        const fields = form.querySelectorAll('.form-control');
        fields.forEach(field => field.style.borderColor = '');
    },

    /**
     * Плавна прокрутка до елемента
     */
    scrollToElement(element, offset = 0) {
        if (!element) return;

        const elementPosition = element.offsetTop - offset;
        window.scrollTo({
            top: elementPosition,
            behavior: 'smooth'
        });
    }
};

// =================== HTTP УТІЛІТИ ===================
const HTTP = {
    /**
     * Базовий HTTP запит з обробкою помилок
     */
    async request(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`HTTP Request Error (${url}):`, error);
            throw error;
        }
    },

    /**
     * GET запит
     */
    async get(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    },

    /**
     * POST запит
     */
    async post(url, data, options = {}) {
        return this.request(url, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PUT запит
     */
    async put(url, data, options = {}) {
        return this.request(url, {
            ...options,
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * DELETE запит
     */
    async delete(url, options = {}) {
        return this.request(url, { ...options, method: 'DELETE' });
    }
};

// =================== ОБРОБКА ПОМИЛОК ===================
const ErrorHandler = {
    /**
     * Обробка API помилок
     */
    handleApiError(error, context = '') {
        console.error(`API Error${context ? ` (${context})` : ''}:`, error);

        let message = 'Виникла помилка при виконанні запиту';

        if (error.message) {
            if (error.message.includes('401')) {
                message = 'Сесія прострочена. Увійдіть знову';
                // Автоматичний редирект на логін через 2 секунди
                setTimeout(() => {
                    Auth.logout();
                }, 2000);
            } else if (error.message.includes('403')) {
                message = 'Недостатньо прав для виконання цієї дії';
            } else if (error.message.includes('404')) {
                message = 'Запитаний ресурс не знайдено';
            } else if (error.message.includes('429')) {
                message = 'Занадто багато запитів. Спробуйте пізніше';
            } else if (error.message.includes('500')) {
                message = 'Помилка сервера. Спробуйте пізніше';
            } else {
                message = error.message;
            }
        }

        return message;
    },

    /**
     * Глобальний обробник помилок
     */
    setup() {
        window.addEventListener('error', (event) => {
            console.error('Global Error:', event.error);
        });

        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled Promise Rejection:', event.reason);
        });
    }
};

// =================== ІНІЦІАЛІЗАЦІЯ ===================
document.addEventListener('DOMContentLoaded', () => {
    ErrorHandler.setup();
});

// =================== ЕКСПОРТ ===================
window.CONFIG = CONFIG;
window.Utils = Utils;
window.Validators = Validators;
window.UI = UI;
window.HTTP = HTTP;
window.ErrorHandler = ErrorHandler;