// common.js - Базові класи для зменшення дублювання

class BaseModal {
    constructor(modalId, formId = null) {
        this.modal = document.getElementById(modalId);
        this.form = formId ? document.getElementById(formId) : null;
        this.closeBtn = this.modal.querySelector('.modal-close');

        this._setupEvents();
    }

    _setupEvents() {
        this.closeBtn?.addEventListener('click', () => this.close());
        window.addEventListener('click', (e) => {
            if (e.target === this.modal) this.close();
        });
    }

    open() {
        this.modal.style.display = 'block';
    }

    close() {
        this.modal.style.display = 'none';
        this.form?.reset();
        this.clearErrors();
    }

    clearErrors() {
        this.modal.querySelectorAll('.field-error').forEach(el => el.remove());
        this.modal.querySelectorAll('.form-control').forEach(field => {
            field.style.borderColor = '';
        });
    }
}

class BaseForm {
    constructor(formElement) {
        this.form = formElement;
    }

    getData() {
        const formData = new FormData(this.form);
        return Object.fromEntries(formData.entries());
    }

    setError(field, message) {
        field.style.borderColor = '#e74c3c';
        let errorEl = field.parentNode.querySelector('.field-error');
        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.className = 'field-error';
            field.parentNode.appendChild(errorEl);
        }
        errorEl.textContent = message;
    }

    validate(rules) {
        const data = this.getData();
        const errors = [];

        for (const [fieldName, rule] of Object.entries(rules)) {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            const value = data[fieldName];

            if (rule.required && !value?.trim()) {
                this.setError(field, rule.message || 'Поле обов\'язкове');
                errors.push(fieldName);
            } else if (rule.validator && !rule.validator(value)) {
                this.setError(field, rule.message);
                errors.push(fieldName);
            }
        }

        return errors.length === 0;
    }
}

// Спрощена версія HTTP без зайвих абстракцій
const api = {
    async request(url, options = {}) {
        const token = localStorage.getItem('access_token');

        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` }),
                ...options.headers
            },
            ...options
        });

        if (response.status === 401) {
            localStorage.clear();
            location.href = '/login';
            return null;
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.message || `HTTP ${response.status}`);
        }

        return response.json();
    },

    get: (url) => api.request(url),
    post: (url, data) => api.request(url, { method: 'POST', body: JSON.stringify(data) }),
    put: (url, data) => api.request(url, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (url) => api.request(url, { method: 'DELETE' })
};

// Спрощені утіліти
const utils = {
    formatTime: (seconds) => new Date(seconds * 1000).toISOString().substr(11, 8),
    timeToSeconds: (timeStr) => timeStr.split(':').reduce((acc, time) => (60 * acc) + +time),
    escapeHtml: (text) => document.createElement('div').textContent = text,
    debounce: (func, ms) => {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func(...args), ms);
        };
    }
};

// Спрощені валідатори
const validators = {
    email: (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email),
    azureUrl: (url) => {
        try {
            const u = new URL(url);
            return u.hostname.includes('.blob.core.windows.net') &&
                   ['.mp4', '.avi', '.mov', '.mkv'].some(ext => url.toLowerCase().endsWith(ext));
        } catch { return false; }
    },
    password: (pwd) => pwd && pwd.length >= 8
};

// Спрощені повідомлення
const notify = (message, type = 'info') => {
    const modal = document.createElement('div');
    modal.className = 'notification-modal';
    modal.innerHTML = `
        <div class="notification-modal-content">
            <h3>${type === 'error' ? 'Помилка' : type === 'success' ? 'Успіх' : 'Інформація'}</h3>
            <p>${utils.escapeHtml(message)}</p>
            <button class="btn btn-success" onclick="this.closest('.notification-modal').remove()">OK</button>
        </div>
    `;
    document.body.appendChild(modal);
    modal.style.display = 'block';
};

const confirm = (message) => new Promise(resolve => {
    const modal = document.createElement('div');
    modal.className = 'notification-modal';
    modal.innerHTML = `
        <div class="notification-modal-content">
            <h3>Підтвердження</h3>
            <p>${utils.escapeHtml(message)}</p>
            <div style="display: flex; gap: 10px; justify-content: center;">
                <button class="btn btn-secondary" onclick="resolve(false)">Скасувати</button>
                <button class="btn btn-success" onclick="resolve(true)">Підтвердити</button>
            </div>
        </div>
    `;

    const buttons = modal.querySelectorAll('button');
    buttons.forEach(btn => {
        btn.onclick = () => {
            modal.remove();
            resolve(btn.textContent === 'Підтвердити');
        };
    });

    document.body.appendChild(modal);
    modal.style.display = 'block';
});

window.BaseModal = BaseModal;
window.BaseForm = BaseForm;
window.api = api;
window.utils = utils;
window.validators = validators;
window.notify = notify;
window.confirm = confirm;