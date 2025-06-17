/**
 * Модуль логіна
 */

class LoginManager {
    constructor() {
        this.elements = {
            form: document.getElementById('login-form'),
            email: document.getElementById('email'),
            password: document.getElementById('password'),
            loginBtn: document.getElementById('login-btn'),
            errorMessage: document.getElementById('error-message')
        };

        this._init();
    }

    _init() {
        this._setupEventListeners();
        this.elements.email.focus();
    }

    _setupEventListeners() {
        this.elements.form.addEventListener('submit', (e) => this._handleLogin(e));
    }

    async _handleLogin(e) {
        e.preventDefault();

        const formData = this._getFormData();

        if (!this._validateForm(formData)) {
            return;
        }

        UI.setButtonState(this.elements.loginBtn, true);
        this._hideError();

        try {
            const data = await HTTP.post('/auth/login', formData);

            Auth.setTokens(data.access_token, data.refresh_token);

            const role = Auth.getCurrentUserRole();
            const homePage = Auth.getRoleBasedHomePage(role);
            window.location.href = homePage;
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'login');
            this._showError(message);
        } finally {
            UI.setButtonState(this.elements.loginBtn, false, 'Увійти');
        }
    }

    _getFormData() {
        return {
            email: this.elements.email.value.trim(),
            password: this.elements.password.value
        };
    }

    _validateForm(data) {
        UI.clearFormErrors(this.elements.form);

        if (!data.email) {
            UI.setFieldValidation(this.elements.email, false, 'Email є обовʼязковим');
            this._showError('Будь ласка, заповніть всі поля');
            return false;
        }

        if (!Validators.isValidEmail(data.email)) {
            UI.setFieldValidation(this.elements.email, false, 'Некоректний email');
            this._showError('Некоректний формат email');
            return false;
        }

        if (!data.password) {
            UI.setFieldValidation(this.elements.password, false, 'Пароль є обовʼязковим');
            this._showError('Будь ласка, заповніть всі поля');
            return false;
        }

        return true;
    }

    _showError(message) {
        this.elements.errorMessage.textContent = message;
        this.elements.errorMessage.classList.remove('hidden');
    }

    _hideError() {
        this.elements.errorMessage.classList.add('hidden');
    }
}

/**
 * Ініціалізація при завантаженні сторінки
 */
document.addEventListener('DOMContentLoaded', () => {
    new LoginManager();
});