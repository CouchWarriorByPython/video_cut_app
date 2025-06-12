// Утилітарні функції для роботи з авторизацією

function getAuthToken() {
    return localStorage.getItem('access_token');
}

function getRefreshToken() {
    return localStorage.getItem('refresh_token');
}

function setTokens(accessToken, refreshToken) {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
}

function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
}

function logout() {
    clearTokens();
    window.location.href = '/login';
}

function isAuthenticated() {
    return !!getAuthToken();
}

// Перевірка авторизації з перенаправленням
async function checkAuthAndRedirect() {
    const currentPath = window.location.pathname;

    // Якщо вже на сторінці логіна і є токен - перенаправляємо на головну
    if (currentPath === '/login' && isAuthenticated()) {
        // Додаткова перевірка - чи токен валідний
        const isValid = await validateToken();
        if (isValid) {
            window.location.href = '/';
            return;
        }
    }

    // Якщо не на сторінці логіна і немає токена - перенаправляємо на логін
    if (currentPath !== '/login' && !isAuthenticated()) {
        window.location.href = '/login';
        return;
    }

    // Якщо не на сторінці логіна і є токен - перевіряємо його валідність
    if (currentPath !== '/login' && isAuthenticated()) {
        const isValid = await validateToken();
        if (!isValid) {
            clearTokens();
            window.location.href = '/login';
        }
    }
}

// Перевірка валідності токена
async function validateToken() {
    const token = getAuthToken();
    if (!token) return false;

    try {
        const response = await fetch('/get_videos', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
        });

        if (response.status === 401) {
            // Спробуємо оновити токен
            const newToken = await refreshAccessToken();
            return !!newToken;
        }

        return response.ok;
    } catch (error) {
        console.error('Помилка валідації токена:', error);
        return false;
    }
}

// Автоматичне оновлення токена
async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
        return null;
    }

    try {
        const response = await fetch('/auth/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                refresh_token: refreshToken
            }),
        });

        if (response.ok) {
            const data = await response.json();
            setTokens(data.access_token, data.refresh_token);
            return data.access_token;
        } else {
            clearTokens();
            return null;
        }
    } catch (error) {
        console.error('Помилка оновлення токена:', error);
        clearTokens();
        return null;
    }
}

// Fetch з автоматичним оновленням токена
async function authenticatedFetch(url, options = {}) {
    let token = getAuthToken();
    if (!token) {
        console.error('Відсутній токен авторизації');
        window.location.href = '/login';
        return null;
    }

    const makeRequest = async (authToken) => {
        return fetch(url, {
            ...options,
            headers: {
                ...options.headers,
                'Authorization': `Bearer ${authToken}`,
            },
        });
    };

    let response = await makeRequest(token);

    // Якщо токен прострочений, спробуємо оновити
    if (response.status === 401) {
        console.log('Токен прострочений, спробуємо оновити...');
        token = await refreshAccessToken();
        if (token) {
            console.log('Токен оновлено, повторюємо запит...');
            response = await makeRequest(token);
        } else {
            console.error('Не вдалося оновити токен');
            window.location.href = '/login';
            return null;
        }
    }

    return response;
}

// Додаємо кнопку logout до навбару
function addLogoutButton() {
    const navbar = document.querySelector('.navbar-menu');
    if (navbar && !document.getElementById('logout-btn')) {
        const logoutBtn = document.createElement('a');
        logoutBtn.id = 'logout-btn';
        logoutBtn.href = '#';
        logoutBtn.className = 'navbar-item';
        logoutBtn.textContent = 'Вийти';
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (confirm('Ви впевнені, що хочете вийти?')) {
                logout();
            }
        });
        navbar.appendChild(logoutBtn);
    }
}

// Ініціалізація при завантаженні DOM
document.addEventListener('DOMContentLoaded', async function() {
    // Перевіряємо авторизацію та перенаправляємо якщо потрібно
    await checkAuthAndRedirect();

    // Додаємо кнопку logout якщо авторизований
    if (isAuthenticated() && window.location.pathname !== '/login') {
        addLogoutButton();
    }
});