const CONFIG = {
    MIN_CLIP_DURATION: 1,
    ROLES: { ANNOTATOR: 'annotator', ADMIN: 'admin', SUPER_ADMIN: 'super_admin' }
};

const PROJECT_NAMES = {
    'motion-det': 'Motion Detection',
    'tracking': 'Tracking & Re-identification',
    'mil-hardware': 'Mil Hardware Detection',
    're-id': 'Re-ID'
};

['error', 'unhandledrejection'].forEach(event => {
    window.addEventListener(event, e => console.error(`Global ${event}:`, e.error || e.reason));
});

class BaseModal {
    constructor(modalId, formId = null) {
        this.modal = document.getElementById(modalId);
        this.form = formId ? document.getElementById(formId) : null;
        this.closeBtn = this.modal.querySelector('.modal-close');
        this._setupEvents();
    }

    _setupEvents() {
        this.closeBtn?.addEventListener('click', () => this.close());
        window.addEventListener('click', e => e.target === this.modal && this.close());
    }

    open() { this.modal.style.display = 'block'; }

    close() {
        this.modal.style.display = 'none';
        this.form?.reset();
        this.clearErrors();
    }

    clearErrors() {
        this.modal.querySelectorAll('.field-error').forEach(el => el.remove());
        this.modal.querySelectorAll('.form-control').forEach(field => field.style.borderColor = '');
    }
}

class BaseForm {
    constructor(formElement) {
        this.form = formElement;
    }

    getData() {
        return Object.fromEntries(new FormData(this.form).entries());
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

        Object.entries(rules).forEach(([fieldName, rule]) => {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            const value = data[fieldName];

            if (rule.required && !value?.trim()) {
                this.setError(field, rule.message || 'Поле обов\'язкове');
                errors.push(fieldName);
            } else if (rule.validator && !rule.validator(value)) {
                this.setError(field, rule.message);
                errors.push(fieldName);
            }
        });

        return errors.length === 0;
    }
}

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

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            // Якщо є повідомлення про помилку від сервера, використовуємо його
            const errorMessage = data.message || data.error || `HTTP ${response.status}`;
            throw new Error(errorMessage);
        }

        return data;
    },

    get: url => api.request(url),
    post: (url, data) => api.request(url, { method: 'POST', body: JSON.stringify(data) }),
    put: (url, data) => api.request(url, { method: 'PUT', body: JSON.stringify(data) }),
    delete: url => api.request(url, { method: 'DELETE' })
};

const utils = {
    formatTime: s => new Date(s * 1000).toISOString().substr(11, 8),
    timeToSeconds: t => t.split(':').reduce((acc, time) => (60 * acc) + +time),
    escapeHtml: text => {
        if (!utils._div) utils._div = document.createElement('div');
        utils._div.textContent = text;
        return utils._div.innerHTML;
    },
    debounce: (func, ms) => {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func(...args), ms);
        };
    },
    generateId: () => 'id_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),

    azureFilePathToUrl: (azureFilePath) => {
        if (!azureFilePath || !azureFilePath.account_name || !azureFilePath.container_name || !azureFilePath.blob_path) {
            return '';
        }
        return `https://${azureFilePath.account_name}.blob.core.windows.net/${azureFilePath.container_name}/${azureFilePath.blob_path}`;
    },

    parseAzureUrl: (url) => {
        try {
            const urlObj = new URL(url);
            const hostname = urlObj.hostname;
            const pathParts = urlObj.pathname.substring(1).split('/');

            const account_name = hostname.split('.')[0];
            const container_name = pathParts[0];
            const blob_path = pathParts.slice(1).join('/');

            return {
                account_name,
                container_name,
                blob_path
            };
        } catch (e) {
            return null;
        }
    },

    compareAzureFilePaths: (path1, path2) => {
        if (!path1 || !path2) return false;
        return path1.account_name === path2.account_name &&
               path1.container_name === path2.container_name &&
               path1.blob_path === path2.blob_path;
    }
};

const validators = {
    email: email => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email),
    azureUrl: url => {
        try {
            const u = new URL(url);
            return u.hostname.includes('.blob.core.windows.net') &&
                   ['.mp4', '.avi', '.mov', '.mkv'].some(ext => url.toLowerCase().endsWith(ext));
        } catch { return false; }
    },
    password: pwd => pwd && pwd.length >= 8
};

const createNotificationModal = (message, type) => {
    const modal = document.createElement('div');
    modal.className = 'notification-modal';
    const title = type === 'error' ? 'Помилка' : type === 'success' ? 'Успіх' : 'Інформація';
    modal.innerHTML = `
        <div class="notification-modal-content">
            <h3>${title}</h3>
            <p>${utils.escapeHtml(message)}</p>
            <button class="btn btn-success" onclick="this.closest('.notification-modal').remove()">OK</button>
        </div>
    `;
    document.body.appendChild(modal);
    modal.style.display = 'block';
};

const notify = (message, type = 'info') => createNotificationModal(message, type);

const confirm = message => new Promise(resolve => {
    const modal = document.createElement('div');
    modal.className = 'notification-modal';
    modal.innerHTML = `
        <div class="notification-modal-content">
            <h3>Підтвердження</h3>
            <p>${utils.escapeHtml(message)}</p>
            <div style="display: flex; gap: 10px; justify-content: center;">
                <button class="btn btn-secondary">Скасувати</button>
                <button class="btn btn-success">Підтвердити</button>
            </div>
        </div>
    `;

    modal.querySelectorAll('button').forEach(btn => {
        btn.onclick = () => {
            modal.remove();
            resolve(btn.textContent === 'Підтвердити');
        };
    });

    document.body.appendChild(modal);
    modal.style.display = 'block';
});

Object.assign(window, { CONFIG, PROJECT_NAMES, BaseModal, BaseForm, api, utils, validators, notify, confirm });