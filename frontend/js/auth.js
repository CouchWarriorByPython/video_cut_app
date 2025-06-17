/**
 * Модуль авторизації та управління сесіями
 */

const Auth = {
    /**
     * Токени доступу
     */
    getAccessToken() {
        return localStorage.getItem('access_token');
    },

    getRefreshToken() {
        return localStorage.getItem('refresh_token');
    },

    setTokens(accessToken, refreshToken) {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
    },

    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    },

    /**
     * Стан авторизації
     */
    isAuthenticated() {
        return !!this.getAccessToken();
    },

    getCurrentUserRole() {
        const token = this.getAccessToken();
        if (!token) return null;

        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.role;
        } catch (error) {
            console.error('Помилка декодування токена:', error);
            return null;
        }
    },

    isAdminRole() {
        const role = this.getCurrentUserRole();
        return [CONFIG.ROLES.ADMIN, CONFIG.ROLES.SUPER_ADMIN].includes(role);
    },

    /**
     * Редиректи залежно від ролі
     */
    getRoleBasedHomePage(role) {
        const rolePages = {
            [CONFIG.ROLES.ANNOTATOR]: CONFIG.PAGES.ANNOTATOR,
            [CONFIG.ROLES.ADMIN]: CONFIG.PAGES.UPLOAD,
            [CONFIG.ROLES.SUPER_ADMIN]: CONFIG.PAGES.UPLOAD
        };
        return rolePages[role] || CONFIG.PAGES.LOGIN;
    },

    hasAccessToPage(path, role) {
        const rolePermissions = {
            [CONFIG.ROLES.ANNOTATOR]: [CONFIG.PAGES.ANNOTATOR, CONFIG.PAGES.FAQ],
            [CONFIG.ROLES.ADMIN]: [CONFIG.PAGES.UPLOAD, CONFIG.PAGES.ANNOTATOR, CONFIG.PAGES.FAQ, CONFIG.PAGES.ADMIN],
            [CONFIG.ROLES.SUPER_ADMIN]: [CONFIG.PAGES.UPLOAD, CONFIG.PAGES.ANNOTATOR, CONFIG.PAGES.FAQ, CONFIG.PAGES.ADMIN]
        };

        const allowedPaths = rolePermissions[role] || [];
        return allowedPaths.includes(path);
    },

    /**
     * Валідація токена
     */
    async validateToken() {
        const token = this.getAccessToken();
        if (!token) return false;

        try {
            const response = await HTTP.get('/get_videos', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            return true;
        } catch (error) {
            if (error.message.includes('401')) {
                const newToken = await this.refreshAccessToken();
                return !!newToken;
            }
            return false;
        }
    },

    async refreshAccessToken() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) return null;

        try {
            const data = await HTTP.post('/auth/refresh', {
                refresh_token: refreshToken
            });

            this.setTokens(data.access_token, data.refresh_token);
            return data.access_token;
        } catch (error) {
            this.clearTokens();
            return null;
        }
    },

    /**
     * Автентифіковані запити
     */
    async authenticatedRequest(url, options = {}) {
        let token = this.getAccessToken();
        if (!token) {
            window.location.href = CONFIG.PAGES.LOGIN;
            return null;
        }

        const makeRequest = async (authToken) => {
            return HTTP.request(url, {
                ...options,
                headers: {
                    ...options.headers,
                    'Authorization': `Bearer ${authToken}`
                }
            });
        };

        try {
            return await makeRequest(token);
        } catch (error) {
            if (error.message.includes('401')) {
                token = await this.refreshAccessToken();
                if (token) {
                    return await makeRequest(token);
                } else {
                    window.location.href = CONFIG.PAGES.LOGIN;
                    return null;
                }
            }
            throw error;
        }
    },

    /**
     * Перевірка доступу та редиректи
     */
    async checkAuthAndRedirect() {
        const currentPath = window.location.pathname;
        const isAuthenticated = this.isAuthenticated();

        if (currentPath === CONFIG.PAGES.LOGIN && isAuthenticated) {
            const isValid = await this.validateToken();
            if (isValid) {
                const role = this.getCurrentUserRole();
                const homePage = this.getRoleBasedHomePage(role);
                window.location.href = homePage;
                return;
            }
        }

        if (currentPath !== CONFIG.PAGES.LOGIN && !isAuthenticated) {
            window.location.href = CONFIG.PAGES.LOGIN;
            return;
        }

        if (currentPath !== CONFIG.PAGES.LOGIN && isAuthenticated) {
            const isValid = await this.validateToken();
            if (!isValid) {
                this.clearTokens();
                window.location.href = CONFIG.PAGES.LOGIN;
                return;
            }

            const role = this.getCurrentUserRole();
            if (!this.hasAccessToPage(currentPath, role)) {
                const homePage = this.getRoleBasedHomePage(role);
                window.location.href = homePage;
                return;
            }
        }
    },

    /**
     * Вихід з системи
     */
    logout() {
        this.clearTokens();
        window.location.href = CONFIG.PAGES.LOGIN;
    },

    /**
     * Додавання кнопок навігації
     */
    addNavigationButtons() {
        const navbar = document.querySelector('.navbar-menu');
        if (!navbar) return;

        const existingAdminBtn = document.querySelector('.navbar-item.admin-link');
        const existingLogoutBtn = document.getElementById('logout-btn');

        if (existingAdminBtn) existingAdminBtn.remove();
        if (existingLogoutBtn) existingLogoutBtn.remove();

        if (this.isAdminRole()) {
            const adminBtn = document.createElement('a');
            adminBtn.href = CONFIG.PAGES.ADMIN;
            adminBtn.className = 'navbar-item admin-link';
            adminBtn.textContent = 'Адмінка';

            if (window.location.pathname === CONFIG.PAGES.ADMIN) {
                adminBtn.classList.add('active');
            }

            navbar.appendChild(adminBtn);
        }

        const logoutBtn = document.createElement('a');
        logoutBtn.id = 'logout-btn';
        logoutBtn.href = '#';
        logoutBtn.className = 'navbar-item';
        logoutBtn.textContent = 'Вийти';
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const confirmed = await showConfirm('Ви впевнені, що хочете вийти?');
            if (confirmed) {
                this.logout();
            }
        });
        navbar.appendChild(logoutBtn);
    }
};

/**
 * Ініціалізація при завантаженні сторінки
 */
document.addEventListener('DOMContentLoaded', async () => {
    await Auth.checkAuthAndRedirect();

    if (Auth.isAuthenticated() && window.location.pathname !== CONFIG.PAGES.LOGIN) {
        Auth.addNavigationButtons();
    }
});

window.Auth = Auth;