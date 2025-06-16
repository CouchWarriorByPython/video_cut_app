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

function getCurrentUserRole() {
    const token = getAuthToken();
    if (!token) return null;

    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.role;
    } catch (error) {
        console.error('Помилка декодування токена:', error);
        return null;
    }
}

function isAdminRole() {
    const role = getCurrentUserRole();
    return ['admin', 'super_admin'].includes(role);
}

async function checkAuthAndRedirect() {
    const currentPath = window.location.pathname;

    if (currentPath === '/login' && isAuthenticated()) {
        const isValid = await validateToken();
        if (isValid) {
            window.location.href = '/';
            return;
        }
    }

    if (currentPath !== '/login' && !isAuthenticated()) {
        window.location.href = '/login';
        return;
    }

    if (currentPath !== '/login' && isAuthenticated()) {
        const isValid = await validateToken();
        if (!isValid) {
            clearTokens();
            window.location.href = '/login';
        }
    }
}

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
            const newToken = await refreshAccessToken();
            return !!newToken;
        }

        return response.ok;
    } catch (error) {
        console.error('Помилка валідації токена:', error);
        return false;
    }
}

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

function addAdminAndLogoutButtons() {
    const navbar = document.querySelector('.navbar-menu');
    if (!navbar) return;

    // Видаляємо існуючі динамічні кнопки щоб уникнути дублювання
    const existingAdminBtn = document.querySelector('.navbar-item.admin-link');
    const existingLogoutBtn = document.getElementById('logout-btn');

    if (existingAdminBtn) existingAdminBtn.remove();
    if (existingLogoutBtn) existingLogoutBtn.remove();

    // Додаємо кнопку адмінки для привілейованих користувачів
    if (isAdminRole()) {
        const adminBtn = document.createElement('a');
        adminBtn.href = '/admin';
        adminBtn.className = 'navbar-item admin-link';
        adminBtn.textContent = 'Адмінка';

        if (window.location.pathname === '/admin') {
            adminBtn.classList.add('active');
        }

        navbar.appendChild(adminBtn);
    }

    // Додаємо кнопку виходу
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

// Зберігаємо стару функцію для зворотної сумісності
function addLogoutButton() {
    addAdminAndLogoutButtons();
}

document.addEventListener('DOMContentLoaded', async function() {
    await checkAuthAndRedirect();

    if (isAuthenticated() && window.location.pathname !== '/login') {
        addAdminAndLogoutButtons();
    }
});