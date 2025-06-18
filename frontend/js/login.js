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
        this._setupEventListeners();
        this.elements.email.focus();
    }

    _setupEventListeners() {
        this.form.form.addEventListener('submit', (e) => this._handleLogin(e));
    }

    async _handleLogin(e) {
        e.preventDefault();

        const validationRules = {
            email: {
                required: true,
                validator: validators.email,
                message: 'Некоректний email'
            },
            password: {
                required: true,
                message: 'Пароль є обов\'язковим'
            }
        };

        if (!this.form.validate(validationRules)) {
            this._showError('Будь ласка, заповніть всі поля коректно');
            return;
        }

        this._setButtonLoading(true);
        this._hideError();

        try {
            const formData = this.form.getData();
            const data = await api.post('/auth/login', formData);

            auth.setTokens(data.access_token, data.refresh_token);

            const homePage = auth.isAdmin ? '/' : '/annotator';
            window.location.href = homePage;
        } catch (error) {
            this._showError(error.message);
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
        this.elements.loginBtn.disabled = loading;
        this.elements.loginBtn.textContent = loading ? '' : 'Увійти';

        if (loading) {
            this.elements.loginBtn.classList.add('loading');
        } else {
            this.elements.loginBtn.classList.remove('loading');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new LoginManager();
});