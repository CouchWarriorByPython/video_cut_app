const auth = {
    get token() { return localStorage.getItem('access_token'); },
    get refreshToken() { return localStorage.getItem('refresh_token'); },

    setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    },

    get role() {
        try {
            return JSON.parse(atob(this.token.split('.')[1])).role;
        } catch { return null; }
    },

    get isAdmin() { return ['admin', 'super_admin'].includes(this.role); },

    async refresh() {
        try {
            const data = await api.post('/auth/refresh', { refresh_token: this.refreshToken });
            this.setTokens(data.access_token, data.refresh_token);
            return true;
        } catch {
            this.logout();
            return false;
        }
    },

    logout() {
        localStorage.clear();
        location.href = '/login';
    },

    async checkAccess() {
        if (!this.token) {
            if (location.pathname !== '/login') this.logout();
            return false;
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
    if (location.pathname === '/login' && auth.token) {
        location.href = auth.isAdmin ? '/' : '/annotator';
        return;
    }

    if (await auth.checkAccess()) {
        auth.createNav();
    }
});

window.auth = auth;