class LoginManager {
    constructor() {
        this.form = new BaseForm(document.getElementById('login-form'));
        this.elements = {
            email: document.getElementById('email'),
            password: document.getElementById('password'),
            loginBtn: document.getElementById('login-btn'),
            errorMessage: document.getElementById('error-message')
        };
        this._init();
    }

    _init() {
        this.form.form.addEventListener('submit', e => this._handleLogin(e));
        this.elements.email.focus();
    }

    async _handleLogin(e) {
        e.preventDefault();

        const validationRules = {
            email: { required: true, validator: validators.email, message: 'Некоректний email' },
            password: { required: true, message: 'Пароль є обов\'язковим' }
        };

        if (!this.form.validate(validationRules)) {
            this._showError('Будь ласка, заповніть всі поля коректно');
            return;
        }

        this._setButtonLoading(true);
        this._hideError();

        try {
            const data = await api.post('/auth/login', this.form.getData());
            auth.setTokens(data.access_token, data.refresh_token);
            window.location.href = auth.isAdmin ? '/' : '/annotator';
        } catch (error) {
            this._showError(error.message || 'Невірний email або пароль');
        } finally {
            this._setButtonLoading(false);
        }
    }

    _showError(message) {
        this.elements.errorMessage.textContent = message;
        this.elements.errorMessage.classList.remove('hidden');
    }

    _hideError() {
        this.elements.errorMessage.classList.add('hidden');
    }

    _setButtonLoading(loading) {
        Object.assign(this.elements.loginBtn, {
            disabled: loading,
            textContent: loading ? '' : 'Увійти'
        });
        this.elements.loginBtn.classList.toggle('loading', loading);
    }
}

document.addEventListener('DOMContentLoaded', () => new LoginManager());