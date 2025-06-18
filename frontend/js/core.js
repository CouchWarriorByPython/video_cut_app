// Константи конфігурації
const CONFIG = {
    SUPPORTED_VIDEO_FORMATS: ['.mp4', '.avi', '.mov', '.mkv'],
    MIN_CLIP_DURATION: 1,
    DATE_FORMAT: 'РРРРММДД',

    ROLES: {
        ANNOTATOR: 'annotator',
        ADMIN: 'admin',
        SUPER_ADMIN: 'super_admin'
    },

    PAGES: {
        LOGIN: '/login',
        UPLOAD: '/',
        ANNOTATOR: '/annotator',
        FAQ: '/faq',
        ADMIN: '/admin'
    }
};

// Проєктні константи
const PROJECT_NAMES = {
    'motion-det': 'Motion Detection',
    'tracking': 'Tracking & Re-identification',
    'mil-hardware': 'Mil Hardware Detection',
    're-id': 'Re-ID'
};

// Глобальна обробка помилок
window.addEventListener('error', (event) => {
    console.error('Global Error:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled Promise Rejection:', event.reason);
});

// Експорт констант
window.CONFIG = CONFIG;
window.PROJECT_NAMES = PROJECT_NAMES;