const CONFIG = {
    MIN_CLIP_DURATION: 1,
    ROLES: { ANNOTATOR: 'annotator', ADMIN: 'admin', SUPER_ADMIN: 'super_admin' }
};

const PROJECT_NAMES = {
    'motion_detection': 'Motion Detection',
    'military_targets_detection_and_tracking_moving': 'Military Targets Moving',
    'military_targets_detection_and_tracking_static': 'Military Targets Static',
    're_id': 'Re-identification'
};

['error', 'unhandledrejection'].forEach(event => {
    window.addEventListener(event, e => console.error(`Global ${event}:`, e.error || e.reason));
});

class BaseModal {
    constructor(modalId, formId = null) {
        this.modal = document.getElementById(modalId);
        this.form = formId ? document.getElementById(formId) : null;

        if (!this.modal) {
            console.warn(`Modal with id "${modalId}" not found`);
            return;
        }

        this.closeBtn = this.modal.querySelector('.modal-close');
        this._setupEvents();
    }

    _setupEvents() {
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }

        window.addEventListener('click', e => {
            if (this.modal && e.target === this.modal) {
                this.close();
            }
        });
    }

    open() {
        if (this.modal) {
            this.modal.style.display = 'block';
        }
    }

    close() {
        if (this.modal) {
            this.modal.style.display = 'none';
            this.form?.reset();
            this.clearErrors();
        }
    }

    clearErrors() {
        if (!this.modal) return;
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
    isRefreshing: false,
    failedQueue: [],
    
    get userId() {
        try {
            const token = localStorage.getItem('access_token');
            if (!token) return null;
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.user_id;
        } catch {
            return null;
        }
    },

    processQueue(error = null) {
        api.failedQueue.forEach(prom => {
            if (error) {
                prom.reject(error);
            } else {
                prom.resolve();
            }
        });
        api.failedQueue = [];
    },

    async request(url, options = {}) {
        // Якщо це запит на refresh - не додаємо токен і не перевіряємо авторизацію
        if (url === '/auth/refresh') {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.message || data.detail || `HTTP ${response.status}`);
            }

            return response.json();
        }

        // Для інших запитів перевіряємо токен
        const token = localStorage.getItem('access_token');

        // Якщо токен прострочений, спробуємо оновити
        if (token && auth.isTokenExpired(token)) {
            if (api.isRefreshing) {
                // Якщо вже оновлюємо токен - чекаємо
                return new Promise((resolve, reject) => {
                    api.failedQueue.push({ resolve, reject });
                }).then(() => api.request(url, options));
            }

            api.isRefreshing = true;
            const refreshed = await auth.refresh();
            api.isRefreshing = false;

            if (refreshed) {
                api.processQueue();
                return api.request(url, options);
            } else {
                api.processQueue(new Error('Failed to refresh token'));
                auth.logout();
                return null;
            }
        }

        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` }),
                ...options.headers
            },
            ...options
        });

        if (response.status === 401) {
            // Спеціальна обробка для ендпоінту логіну - не робимо logout, а кидаємо помилку
            if (url === '/auth/login') {
                const data = await response.json().catch(() => ({}));
                const errorMessage = data.message || data.detail || 'Невірний email або пароль';
                throw new Error(errorMessage);
            }

            // Якщо отримали 401 і не намагалися оновити токен
            if (!api.isRefreshing && token) {
                api.isRefreshing = true;
                const refreshed = await auth.refresh();
                api.isRefreshing = false;

                if (refreshed) {
                    api.processQueue();
                    return api.request(url, options);
                } else {
                    api.processQueue(new Error('Unauthorized'));
                    auth.logout();
                    return null;
                }
            }

            // Якщо немає токена або вже намагалися оновити
            auth.logout();
            return null;
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            let errorMessage = data.message || data.detail || data.error || `HTTP ${response.status}`;
            
            // Якщо є детальні помилки валідації, додаємо їх до повідомлення
            if (data.errors && Array.isArray(data.errors)) {
                const fieldErrors = data.errors.map(err => `${err.field}: ${err.message}`).join('; ');
                errorMessage = `${errorMessage}. Деталі: ${fieldErrors}`;
            }
            
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
            return u.hostname.includes('.blob.core.windows.net');
        } catch { return false; }
    },
    azureFolderUrl: url => {
        try {
            const u = new URL(url);
            return u.hostname.includes('.blob.core.windows.net') && url.endsWith('/');
        } catch { return false; }
    },
    password: pwd => pwd && pwd.length >= 8
};

const createNotificationModal = (message, type) => {
    const modal = document.createElement('div');
    modal.className = 'notification-modal';
    const title = type === 'error' ? 'Помилка' : type === 'success' ? 'Успіх' : 'Інформація';
    
    // Перетворюємо \n на <br> для правильного відображення багаторядкових повідомлень
    const formattedMessage = utils.escapeHtml(message).replace(/\n/g, '<br>');
    
    modal.innerHTML = `
        <div class="notification-modal-content">
            <h3>${title}</h3>
            <p>${formattedMessage}</p>
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