const auth = {
    get token() { return localStorage.getItem('access_token'); },
    get refreshToken() { return localStorage.getItem('refresh_token'); },

    setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    },

    get role() {
        try {
            const token = this.token;
            if (!token) return null;
            return JSON.parse(atob(token.split('.')[1])).role;
        } catch { return null; }
    },

    get isAdmin() { return ['admin', 'super_admin'].includes(this.role); },

    isTokenExpired(token) {
        try {
            if (!token) return true;
            const payload = JSON.parse(atob(token.split('.')[1]));
            const exp = payload.exp;
            if (!exp) return false;
            // Перевіряємо чи токен прострочений (з запасом в 60 секунд)
            return (exp * 1000) < (Date.now() + 60000);
        } catch {
            return true;
        }
    },

    async refresh() {
        try {
            const refreshToken = this.refreshToken;
            if (!refreshToken) {
                console.log('No refresh token available');
                return false;
            }
            
            if (this.isTokenExpired(refreshToken)) {
                console.log('Refresh token is expired');
                return false;
            }

            console.log('Attempting to refresh access token');
            const data = await api.post('/auth/refresh', { refresh_token: refreshToken });
            if (data && data.access_token && data.refresh_token) {
                this.setTokens(data.access_token, data.refresh_token);
                console.log('Tokens refreshed successfully');
                return true;
            }
            console.log('Refresh response invalid');
            return false;
        } catch (error) {
            console.error('Refresh failed:', error.message);
            return false;
        }
    },

    logout() {
        console.log('Logging out and clearing all tokens');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        location.href = '/login';
    },

    async checkAccess() {
        const token = this.token;
        const refreshToken = this.refreshToken;

        // Якщо немає токена
        if (!token) {
            if (location.pathname !== '/login') this.logout();
            return false;
        }

        // Якщо refresh токен прострочений, очищаємо все та перенаправляємо на логін
        if (refreshToken && this.isTokenExpired(refreshToken)) {
            console.log('Refresh token expired, clearing storage');
            this.logout();
            return false;
        }

        // Якщо access токен прострочений, спробуємо оновити
        if (this.isTokenExpired(token)) {
            const refreshed = await this.refresh();
            if (!refreshed) {
                this.logout();
                return false;
            }
        }

        const permissions = {
            annotator: ['/annotator', '/faq'],
            admin: ['/', '/annotator', '/faq', '/admin'],
            super_admin: ['/', '/annotator', '/faq', '/admin']
        };

        const allowed = permissions[this.role] || [];
        if (!allowed.includes(location.pathname)) {
            location.href = allowed[0] || '/login';
            return false;
        }
        return true;
    },

    createNav() {
        const nav = document.querySelector('.navbar-menu');
        if (!nav || !this.role) return;

        const links = { '/': 'Завантажити відео', '/annotator': 'Анотувати відео', '/faq': 'FAQ' };

        nav.innerHTML = Object.entries(links)
            .filter(([path]) => this.hasAccess(path))
            .map(([path, label]) =>
                `<a href="${path}" class="navbar-item ${location.pathname === path ? 'active' : ''}">${label}</a>`)
            .join('');

        if (this.isAdmin) {
            nav.innerHTML += `<a href="/admin" class="navbar-item admin-link ${location.pathname === '/admin' ? 'active' : ''}">Адмінка</a>`;
        }

        nav.innerHTML += `<a href="#" class="navbar-item" onclick="auth.logout()">Вийти</a>`;
    },

    hasAccess(path) {
        const permissions = {
            annotator: ['/annotator', '/faq'],
            admin: ['/', '/annotator', '/faq', '/admin'],
            super_admin: ['/', '/annotator', '/faq', '/admin']
        };
        return (permissions[this.role] || []).includes(path);
    }
};

document.addEventListener('DOMContentLoaded', async () => {
    // Перевіряємо токен перед будь-якими діями
    if (auth.token && auth.isTokenExpired(auth.token)) {
        const refreshed = await auth.refresh();
        if (!refreshed) {
            auth.logout();
            return;
        }
    }

    if (location.pathname === '/login' && auth.token && !auth.isTokenExpired(auth.token)) {
        location.href = auth.isAdmin ? '/' : '/annotator';
        return;
    }

    if (await auth.checkAccess()) {
        auth.createNav();
    }
});

window.auth = auth;