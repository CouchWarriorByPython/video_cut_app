document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('login-form');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const loginBtn = document.getElementById('login-btn');
    const errorMessage = document.getElementById('error-message');

    loginForm.addEventListener('submit', handleLogin);

    async function handleLogin(e) {
        e.preventDefault();

        const email = emailInput.value.trim();
        const password = passwordInput.value;

        if (!email || !password) {
            showError('Будь ласка, заповніть всі поля');
            return;
        }

        setLoading(true);
        hideError();

        try {
            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                }),
            });

            const data = await response.json();

            if (response.ok) {
                // Зберігаємо токени
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);

                // Перенаправляємо на головну сторінку
                window.location.href = '/';
            } else {
                showError(data.message || 'Помилка входу');
            }
        } catch (error) {
            console.error('Помилка логіна:', error);
            showError('Помилка з\'єднання з сервером');
        } finally {
            setLoading(false);
        }
    }

    function setLoading(loading) {
        loginBtn.disabled = loading;
        if (loading) {
            loginBtn.textContent = '';
        } else {
            loginBtn.textContent = 'Увійти';
        }
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }

    // Автофокус на email
    emailInput.focus();
});