const currentUsers = [];
const currentCvatSettings = [];
let currentEditingUser = null;
let currentEditingProject = null;

const UI = {
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">×</button>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    },

    showConfirm(message) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Підтвердження</h3>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" data-action="cancel">Скасувати</button>
                        <button class="btn btn-danger" data-action="confirm">Підтвердити</button>
                    </div>
                </div>
            `;

            modal.addEventListener('click', (e) => {
                if (e.target.dataset.action === 'confirm') {
                    modal.remove();
                    resolve(true);
                } else if (e.target.dataset.action === 'cancel' || e.target === modal) {
                    modal.remove();
                    resolve(false);
                }
            });

            document.body.appendChild(modal);
            modal.style.display = 'block';
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    initializeAdmin();
});

async function initializeAdmin() {
    try {
        await checkAuthAndRedirect();

        if (!isAuthenticated()) {
            return;
        }

        const hasAccess = await checkAdminAccess();
        if (!hasAccess) {
            window.location.href = '/';
            return;
        }

        setupEventListeners();
        await loadAdminData();

    } catch (error) {
        console.error('Помилка ініціалізації адмін панелі:', error);
        UI.showNotification('Помилка завантаження адмін панелі', 'error');
    }
}

async function checkAdminAccess() {
    try {
        const response = await authenticatedFetch('/admin/stats');
        return response?.ok ?? false;
    } catch (error) {
        return false;
    }
}

function setupEventListeners() {
    const elements = {
        tabButtons: document.querySelectorAll('.tab-button'),
        addUserBtn: document.getElementById('add-user-btn'),
        saveUserBtn: document.getElementById('save-user-btn'),
        cancelUserBtn: document.getElementById('cancel-user-btn'),
        saveEditUserBtn: document.getElementById('save-edit-user-btn'),
        cancelEditUserBtn: document.getElementById('cancel-edit-user-btn'),
        resetCvatBtn: document.getElementById('reset-cvat-btn'),
        saveCvatBtn: document.getElementById('save-cvat-btn'),
        cancelCvatBtn: document.getElementById('cancel-cvat-btn'),
        modalCloses: document.querySelectorAll('.modal-close')
    };

    elements.tabButtons.forEach(button => {
        button.addEventListener('click', handleTabSwitch);
    });

    elements.addUserBtn.addEventListener('click', openAddUserModal);
    elements.saveUserBtn.addEventListener('click', handleSaveUser);
    elements.cancelUserBtn.addEventListener('click', closeUserModal);
    elements.saveEditUserBtn.addEventListener('click', handleSaveEditUser);
    elements.cancelEditUserBtn.addEventListener('click', closeEditUserModal);
    elements.resetCvatBtn.addEventListener('click', handleResetCvatSettings);
    elements.saveCvatBtn.addEventListener('click', handleSaveCvatSettings);
    elements.cancelCvatBtn.addEventListener('click', closeCvatModal);

    elements.modalCloses.forEach(closeBtn => {
        closeBtn.addEventListener('click', closeAllModals);
    });

    window.addEventListener('click', handleWindowClick);
}

function handleTabSwitch(e) {
    const tabName = e.target.dataset.tab;

    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    e.target.classList.add('active');

    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

async function loadAdminData() {
    showLoading('Завантаження даних...');

    try {
        await Promise.all([
            loadStatistics(),
            loadUsers(),
            loadCvatSettings()
        ]);
    } catch (error) {
        console.error('Помилка завантаження даних:', error);
        UI.showNotification('Помилка завантаження даних', 'error');
    } finally {
        hideLoading();
    }
}

async function loadStatistics() {
    try {
        const response = await authenticatedFetch('/admin/stats');
        if (!response?.ok) {
            throw new Error('Помилка завантаження статистики');
        }

        const stats = await response.json();
        updateStatistics(stats);

    } catch (error) {
        console.error('Помилка завантаження статистики:', error);
    }
}

function updateStatistics(stats) {
    const elements = {
        totalUsers: document.getElementById('total-users'),
        activeUsers: document.getElementById('active-users'),
        totalVideos: document.getElementById('total-videos'),
        processingVideos: document.getElementById('processing-videos')
    };

    elements.totalUsers.textContent = stats.total_users;
    elements.activeUsers.textContent = stats.active_users;
    elements.totalVideos.textContent = stats.total_videos;
    elements.processingVideos.textContent = stats.processing_videos;
}

async function loadUsers() {
    try {
        const response = await authenticatedFetch('/admin/users');
        if (!response?.ok) {
            throw new Error('Помилка завантаження користувачів');
        }

        const users = await response.json();

        currentUsers.length = 0;
        currentUsers.push(...users);

        renderUsersTable();

    } catch (error) {
        console.error('Помилка завантаження користувачів:', error);
        UI.showNotification('Помилка завантаження користувачів', 'error');
    }
}

function renderUsersTable() {
    const tbody = document.querySelector('#users-table tbody');
    tbody.innerHTML = '';

    currentUsers.forEach(user => {
        const row = document.createElement('tr');

        row.innerHTML = `
            <td>${escapeHtml(user.email)}</td>
            <td><span class="role-badge ${user.role}">${getRoleDisplayName(user.role)}</span></td>
            <td><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Активний' : 'Неактивний'}</span></td>
            <td>${formatDate(user.created_at)}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-icon" data-action="edit-user" data-user-id="${user.id}" title="Редагувати">
                        ✏️
                    </button>
                    <button class="btn btn-danger btn-icon" data-action="delete-user" data-user-id="${user.id}" title="Видалити">
                        🗑️
                    </button>
                </div>
            </td>
        `;

        row.addEventListener('click', handleUserActions);
        tbody.appendChild(row);
    });
}

function handleUserActions(e) {
    const action = e.target.dataset.action;
    const userId = e.target.dataset.userId;

    if (action === 'edit-user') {
        openEditUserModal(userId);
    } else if (action === 'delete-user') {
        deleteUser(userId);
    }
}

function openEditUserModal(userId) {
    const user = currentUsers.find(u => u.id === userId);
    if (!user) return;

    currentEditingUser = user;

    const elements = {
        title: document.getElementById('edit-user-modal-title'),
        email: document.getElementById('edit-user-email'),
        password: document.getElementById('edit-user-password'),
        role: document.getElementById('edit-user-role'),
        modal: document.getElementById('edit-user-modal')
    };

    elements.title.textContent = `Редагувати ${user.email}`;
    elements.email.value = user.email;
    elements.password.value = '';
    elements.role.value = user.role;
    elements.modal.style.display = 'block';
}

async function handleSaveEditUser() {
    if (!currentEditingUser) return;

    const formData = {
        email: document.getElementById('edit-user-email').value.trim(),
        password: document.getElementById('edit-user-password').value,
        role: document.getElementById('edit-user-role').value
    };

    const validation = validateEditUserForm(formData);
    if (!validation.valid) {
        UI.showNotification(validation.message, 'error');
        return;
    }

    try {
        const requestData = {
            email: formData.email,
            role: formData.role
        };

        if (formData.password) {
            requestData.password = formData.password;
        }

        const response = await authenticatedFetch(`/admin/users/${currentEditingUser.id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
        });

        if (!response?.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Помилка оновлення користувача');
        }

        UI.showNotification('Користувача успішно оновлено', 'success');
        closeEditUserModal();
        await loadUsers();

    } catch (error) {
        console.error('Помилка оновлення користувача:', error);
        UI.showNotification(error.message, 'error');
    }
}

function validateEditUserForm({ email, password, role }) {
    if (!email || !role) {
        return { valid: false, message: 'Email та роль є обов\'язковими' };
    }

    if (password && password.length < 8) {
        return { valid: false, message: 'Пароль повинен містити мінімум 8 символів' };
    }

    return { valid: true };
}

function closeEditUserModal() {
    document.getElementById('edit-user-modal').style.display = 'none';
    document.getElementById('edit-user-form').reset();
    currentEditingUser = null;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getRoleDisplayName(role) {
    const roleNames = {
        'super_admin': 'Super Admin',
        'admin': 'Admin',
        'annotator': 'Annotator'
    };
    return roleNames[role] || role;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('uk-UA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function openAddUserModal() {
    currentEditingUser = null;
    document.getElementById('user-modal-title').textContent = 'Додати користувача';
    document.getElementById('user-form').reset();
    document.getElementById('user-modal').style.display = 'block';
}

async function deleteUser(userId) {
    const user = currentUsers.find(u => u.id === userId);
    if (!user) return;

    const confirmed = await UI.showConfirm(`Видалити користувача ${user.email}?\n\nЦя дія незворотна.`);
    if (!confirmed) return;

    try {
        const response = await authenticatedFetch(`/admin/users/${userId}`, {
            method: 'DELETE',
        });

        if (!response?.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Помилка видалення користувача');
        }

        UI.showNotification('Користувача успішно видалено', 'success');
        await loadUsers();

    } catch (error) {
        console.error('Помилка видалення користувача:', error);
        UI.showNotification(error.message, 'error');
    }
}

async function handleSaveUser() {
    const formData = {
        email: document.getElementById('user-email').value.trim(),
        password: document.getElementById('user-password').value,
        role: document.getElementById('user-role').value
    };

    const validation = validateUserForm(formData);
    if (!validation.valid) {
        UI.showNotification(validation.message, 'error');
        return;
    }

    try {
        const response = await authenticatedFetch('/admin/users', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
        });

        if (!response?.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Помилка створення користувача');
        }

        UI.showNotification('Користувача успішно створено', 'success');
        closeUserModal();
        await loadUsers();

    } catch (error) {
        console.error('Помилка створення користувача:', error);
        UI.showNotification(error.message, 'error');
    }
}

function validateUserForm({ email, password, role }) {
    if (!email || !password || !role) {
        return { valid: false, message: 'Заповніть всі поля' };
    }

    if (password.length < 8) {
        return { valid: false, message: 'Пароль повинен містити мінімум 8 символів' };
    }

    return { valid: true };
}

function closeUserModal() {
    document.getElementById('user-modal').style.display = 'none';
    document.getElementById('user-form').reset();
    currentEditingUser = null;
}

async function loadCvatSettings() {
    try {
        const response = await authenticatedFetch('/admin/cvat-settings');
        if (!response?.ok) {
            throw new Error('Помилка завантаження налаштувань CVAT');
        }

        const settings = await response.json();

        currentCvatSettings.length = 0;
        currentCvatSettings.push(...settings);

        renderCvatSettings();

    } catch (error) {
        console.error('Помилка завантаження налаштувань CVAT:', error);
        UI.showNotification('Помилка завантаження налаштувань CVAT', 'error');
    }
}

function renderCvatSettings() {
    const container = document.getElementById('cvat-settings-grid');
    container.innerHTML = '';

    const projectNames = {
        'motion-det': 'Motion Detection',
        'tracking': 'Tracking & Re-identification',
        'mil-hardware': 'Mil Hardware Detection',
        're-id': 'Re-ID'
    };

    currentCvatSettings.forEach(setting => {
        const card = document.createElement('div');
        card.className = 'cvat-project-card';
        card.innerHTML = `
            <div class="project-header">
                <h3 class="project-name">${projectNames[setting.project_name] || setting.project_name}</h3>
                <button class="btn btn-icon" data-action="edit-cvat" data-project="${setting.project_name}" title="Редагувати">
                    ✏️
                </button>
            </div>
            <div class="project-settings">
                <div class="setting-item">
                    <span class="setting-label">Project ID:</span>
                    <span class="setting-value">${setting.project_id}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Overlap:</span>
                    <span class="setting-value">${setting.overlap}%</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Segment Size:</span>
                    <span class="setting-value">${setting.segment_size}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Image Quality:</span>
                    <span class="setting-value">${setting.image_quality}%</span>
                </div>
            </div>
        `;

        card.addEventListener('click', handleCvatActions);
        container.appendChild(card);
    });
}

function handleCvatActions(e) {
    const action = e.target.dataset.action;
    const projectName = e.target.dataset.project;

    if (action === 'edit-cvat') {
        editCvatSettings(projectName);
    }
}

function editCvatSettings(projectName) {
    const setting = currentCvatSettings.find(s => s.project_name === projectName);
    if (!setting) return;

    currentEditingProject = projectName;

    const projectNames = {
        'motion-det': 'Motion Detection',
        'tracking': 'Tracking & Re-identification',
        'mil-hardware': 'Mil Hardware Detection',
        're-id': 'Re-ID'
    };

    const elements = {
        title: document.getElementById('cvat-modal-title'),
        projectId: document.getElementById('cvat-project-id'),
        overlap: document.getElementById('cvat-overlap'),
        segmentSize: document.getElementById('cvat-segment-size'),
        imageQuality: document.getElementById('cvat-image-quality'),
        modal: document.getElementById('cvat-modal')
    };

    elements.title.textContent = `Редагувати ${projectNames[projectName]}`;
    elements.projectId.value = setting.project_id;
    elements.overlap.value = setting.overlap;
    elements.segmentSize.value = setting.segment_size;
    elements.imageQuality.value = setting.image_quality;
    elements.modal.style.display = 'block';
}

async function handleSaveCvatSettings() {
    if (!currentEditingProject) return;

    const formData = {
        projectId: parseInt(document.getElementById('cvat-project-id').value),
        overlap: parseInt(document.getElementById('cvat-overlap').value),
        segmentSize: parseInt(document.getElementById('cvat-segment-size').value),
        imageQuality: parseInt(document.getElementById('cvat-image-quality').value)
    };

    const validation = validateCvatForm(formData);
    if (!validation.valid) {
        UI.showNotification(validation.message, 'error');
        return;
    }

    try {
        const response = await authenticatedFetch(`/admin/cvat-settings/${currentEditingProject}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                project_id: formData.projectId,
                overlap: formData.overlap,
                segment_size: formData.segmentSize,
                image_quality: formData.imageQuality
            }),
        });

        if (!response?.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Помилка збереження налаштувань');
        }

        UI.showNotification('Налаштування успішно збережені', 'success');
        closeCvatModal();
        await loadCvatSettings();

    } catch (error) {
        console.error('Помилка збереження налаштувань CVAT:', error);
        UI.showNotification(error.message, 'error');
    }
}

function validateCvatForm({ projectId, overlap, segmentSize, imageQuality }) {
    if (!projectId || projectId < 1 || projectId > 1000) {
        return { valid: false, message: 'Project ID повинен бути між 1 та 1000' };
    }

    if (overlap < 0 || overlap > 100) {
        return { valid: false, message: 'Overlap повинен бути між 0 та 100' };
    }

    if (segmentSize < 50 || segmentSize > 2000) {
        return { valid: false, message: 'Segment Size повинен бути між 50 та 2000' };
    }

    if (imageQuality < 1 || imageQuality > 100) {
        return { valid: false, message: 'Image Quality повинен бути між 1 та 100' };
    }

    return { valid: true };
}

async function handleResetCvatSettings() {
    const confirmed = await UI.showConfirm('Скинути всі налаштування CVAT до дефолтних значень?\n\nЦе оновить всі проєкти.');
    if (!confirmed) return;

    const defaultSettings = [
        { project_name: 'motion-det', project_id: 5, overlap: 5, segment_size: 400, image_quality: 100 },
        { project_name: 'tracking', project_id: 6, overlap: 5, segment_size: 400, image_quality: 100 },
        { project_name: 'mil-hardware', project_id: 7, overlap: 5, segment_size: 400, image_quality: 100 },
        { project_name: 're-id', project_id: 8, overlap: 5, segment_size: 400, image_quality: 100 }
    ];

    try {
        const updatePromises = defaultSettings.map(setting =>
            authenticatedFetch(`/admin/cvat-settings/${setting.project_name}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    project_id: setting.project_id,
                    overlap: setting.overlap,
                    segment_size: setting.segment_size,
                    image_quality: setting.image_quality
                }),
            })
        );

        const responses = await Promise.all(updatePromises);

        const failedRequests = responses.filter(response => !response?.ok);
        if (failedRequests.length > 0) {
            throw new Error('Деякі налаштування не вдалося оновити');
        }

        UI.showNotification('Налаштування успішно скинуті до дефолтних значень', 'success');
        await loadCvatSettings();

    } catch (error) {
        console.error('Помилка скидання налаштувань:', error);
        UI.showNotification(error.message, 'error');
    }
}

function closeCvatModal() {
    document.getElementById('cvat-modal').style.display = 'none';
    currentEditingProject = null;
}

function closeAllModals() {
    closeUserModal();
    closeEditUserModal();
    closeCvatModal();
}

function handleWindowClick(e) {
    if (e.target.classList.contains('modal')) {
        closeAllModals();
    }
}

function showLoading(message) {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.id = 'loading-overlay';
    overlay.innerHTML = `
        <div class="loading-content">
            <div class="loading-spinner"></div>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    overlay?.remove();
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

function addLogoutButton() {
    const navbar = document.querySelector('.navbar-menu');
    if (!navbar || document.getElementById('logout-btn')) return;

    // Додаємо кнопку адмінки для привілейованих користувачів
    if (isAdminRole()) {
        const adminBtn = document.createElement('a');
        adminBtn.href = '/admin';
        adminBtn.className = 'navbar-item';
        adminBtn.textContent = 'Адмінка';

        // Додаємо active клас якщо знаходимося на сторінці адмінки
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