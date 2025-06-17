class AdminPanel {
    constructor() {
        this.state = this._initializeState();
        this.elements = this._initializeElements();
        
        this._init();
    }

    _initializeState() {
        return {
            currentUsers: [],
            currentCvatSettings: [],
            currentEditingUser: null,
            currentEditingProject: null
        };
    }

    _initializeElements() {
        return {
            tabs: {
                buttons: document.querySelectorAll('.tab-button'),
                contents: document.querySelectorAll('.tab-content')
            },
            users: {
                addBtn: document.getElementById('add-user-btn'),
                table: document.getElementById('users-table'),
                modal: document.getElementById('user-modal'),
                modalTitle: document.getElementById('user-modal-title'),
                form: document.getElementById('user-form'),
                email: document.getElementById('user-email'),
                password: document.getElementById('user-password'),
                role: document.getElementById('user-role'),
                saveBtn: document.getElementById('save-user-btn'),
                cancelBtn: document.getElementById('cancel-user-btn')
            },
            editUser: {
                modal: document.getElementById('edit-user-modal'),
                modalTitle: document.getElementById('edit-user-modal-title'),
                form: document.getElementById('edit-user-form'),
                email: document.getElementById('edit-user-email'),
                password: document.getElementById('edit-user-password'),
                role: document.getElementById('edit-user-role'),
                saveBtn: document.getElementById('save-edit-user-btn'),
                cancelBtn: document.getElementById('cancel-edit-user-btn')
            },
            cvat: {
                resetBtn: document.getElementById('reset-cvat-btn'),
                settingsGrid: document.getElementById('cvat-settings-grid'),
                modal: document.getElementById('cvat-modal'),
                modalTitle: document.getElementById('cvat-modal-title'),
                form: document.getElementById('cvat-form'),
                projectId: document.getElementById('cvat-project-id'),
                overlap: document.getElementById('cvat-overlap'),
                segmentSize: document.getElementById('cvat-segment-size'),
                imageQuality: document.getElementById('cvat-image-quality'),
                saveBtn: document.getElementById('save-cvat-btn'),
                cancelBtn: document.getElementById('cancel-cvat-btn')
            },
            stats: {
                totalUsers: document.getElementById('total-users'),
                activeUsers: document.getElementById('active-users'),
                totalVideos: document.getElementById('total-videos'),
                processingVideos: document.getElementById('processing-videos')
            },
            modalCloses: document.querySelectorAll('.modal-close')
        };
    }

    async _init() {
        try {
            await Auth.checkAuthAndRedirect();

            if (!Auth.isAuthenticated()) {
                return;
            }

            const hasAccess = await this._checkAdminAccess();
            if (!hasAccess) {
                window.location.href = '/';
                return;
            }

            this._setupEventListeners();
            await this._loadAdminData();

        } catch (error) {
            console.error('Помилка ініціалізації адмін панелі:', error);
            await showNotification('Помилка завантаження адмін панелі', 'error');
        }
    }

    async _checkAdminAccess() {
        try {
            const response = await Auth.authenticatedRequest('/admin/stats');
            return !!response;
        } catch (error) {
            return false;
        }
    }

    _setupEventListeners() {
        this.elements.tabs.buttons.forEach(button => {
            button.addEventListener('click', (e) => this._handleTabSwitch(e));
        });

        this.elements.users.addBtn.addEventListener('click', () => this._openAddUserModal());
        this.elements.users.saveBtn.addEventListener('click', () => this._handleSaveUser());
        this.elements.users.cancelBtn.addEventListener('click', () => this._closeUserModal());

        this.elements.editUser.saveBtn.addEventListener('click', () => this._handleSaveEditUser());
        this.elements.editUser.cancelBtn.addEventListener('click', () => this._closeEditUserModal());

        this.elements.cvat.resetBtn.addEventListener('click', () => this._handleResetCvatSettings());
        this.elements.cvat.saveBtn.addEventListener('click', () => this._handleSaveCvatSettings());
        this.elements.cvat.cancelBtn.addEventListener('click', () => this._closeCvatModal());

        this.elements.modalCloses.forEach(closeBtn => {
            closeBtn.addEventListener('click', () => this._closeAllModals());
        });

        window.addEventListener('click', (e) => this._handleWindowClick(e));
    }

    _handleTabSwitch(e) {
        const tabName = e.target.dataset.tab;

        this.elements.tabs.buttons.forEach(btn => {
            btn.classList.remove('active');
        });
        e.target.classList.add('active');

        this.elements.tabs.contents.forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');
    }

    async _loadAdminData() {
        UI.showLoader('Завантаження даних...');

        try {
            await Promise.all([
                this._loadStatistics(),
                this._loadUsers(),
                this._loadCvatSettings()
            ]);
        } catch (error) {
            console.error('Помилка завантаження даних:', error);
            await showNotification('Помилка завантаження даних', 'error');
        } finally {
            UI.hideLoader();
        }
    }

    async _loadStatistics() {
        try {
            const stats = await Auth.authenticatedRequest('/admin/stats');
            if (!stats) return;

            this._updateStatistics(stats);
        } catch (error) {
            console.error('Помилка завантаження статистики:', error);
        }
    }

    _updateStatistics(stats) {
        this.elements.stats.totalUsers.textContent = stats.total_users;
        this.elements.stats.activeUsers.textContent = stats.active_users;
        this.elements.stats.totalVideos.textContent = stats.total_videos;
        this.elements.stats.processingVideos.textContent = stats.processing_videos;
    }

    async _loadUsers() {
        try {
            const users = await Auth.authenticatedRequest('/admin/users');
            if (!users) return;

            this.state.currentUsers.length = 0;
            this.state.currentUsers.push(...users);

            this._renderUsersTable();
        } catch (error) {
            console.error('Помилка завантаження користувачів:', error);
            await showNotification('Помилка завантаження користувачів', 'error');
        }
    }

    _renderUsersTable() {
        const tbody = this.elements.users.table.querySelector('tbody');
        tbody.innerHTML = '';

        this.state.currentUsers.forEach(user => {
            const row = document.createElement('tr');

            row.innerHTML = `
                <td>${Utils.escapeHtml(user.email)}</td>
                <td><span class="role-badge ${user.role}">${this._getRoleDisplayName(user.role)}</span></td>
                <td><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Активний' : 'Неактивний'}</span></td>
                <td>${Utils.formatDate(user.created_at)}</td>
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

            row.addEventListener('click', (e) => this._handleUserActions(e));
            tbody.appendChild(row);
        });
    }

    _handleUserActions(e) {
        const action = e.target.dataset.action;
        const userId = e.target.dataset.userId;

        if (action === 'edit-user') {
            this._openEditUserModal(userId);
        } else if (action === 'delete-user') {
            this._deleteUser(userId);
        }
    }

    _openAddUserModal() {
        this.state.currentEditingUser = null;
        this.elements.users.modalTitle.textContent = 'Додати користувача';
        this.elements.users.form.reset();
        UI.clearFormErrors(this.elements.users.form);
        this.elements.users.modal.style.display = 'block';
    }

    _openEditUserModal(userId) {
        const user = this.state.currentUsers.find(u => u.id === userId);
        if (!user) return;

        this.state.currentEditingUser = user;

        this.elements.editUser.modalTitle.textContent = `Редагувати ${user.email}`;
        this.elements.editUser.email.value = user.email;
        this.elements.editUser.password.value = '';
        this.elements.editUser.role.value = user.role;
        UI.clearFormErrors(this.elements.editUser.form);
        this.elements.editUser.modal.style.display = 'block';
    }

    async _handleSaveUser() {
        const formData = {
            email: this.elements.users.email.value.trim(),
            password: this.elements.users.password.value,
            role: this.elements.users.role.value
        };

        const validation = this._validateUserForm(formData);
        if (!validation.valid) {
            await showNotification(validation.message, 'error');
            return;
        }

        try {
            const data = await Auth.authenticatedRequest('/admin/users', {
                method: 'POST',
                body: JSON.stringify(formData)
            });

            if (!data) return;

            await showNotification('Користувача успішно створено', 'success');
            this._closeUserModal();
            await this._loadUsers();
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'create user');
            await showNotification(message, 'error');
        }
    }

    async _handleSaveEditUser() {
        if (!this.state.currentEditingUser) return;

        const formData = {
            email: this.elements.editUser.email.value.trim(),
            password: this.elements.editUser.password.value,
            role: this.elements.editUser.role.value
        };

        const validation = this._validateEditUserForm(formData);
        if (!validation.valid) {
            await showNotification(validation.message, 'error');
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

            const data = await Auth.authenticatedRequest(`/admin/users/${this.state.currentEditingUser.id}`, {
                method: 'PUT',
                body: JSON.stringify(requestData)
            });

            if (!data) return;

            await showNotification('Користувача успішно оновлено', 'success');
            this._closeEditUserModal();
            await this._loadUsers();
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'update user');
            await showNotification(message, 'error');
        }
    }

    async _deleteUser(userId) {
        const user = this.state.currentUsers.find(u => u.id === userId);
        if (!user) return;

        const confirmed = await showConfirm(`Видалити користувача ${user.email}?\n\nЦя дія незворотна.`);
        if (!confirmed) return;

        try {
            const data = await Auth.authenticatedRequest(`/admin/users/${userId}`, {
                method: 'DELETE'
            });

            if (!data) return;

            await showNotification('Користувача успішно видалено', 'success');
            await this._loadUsers();
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'delete user');
            await showNotification(message, 'error');
        }
    }

    _validateUserForm({ email, password, role }) {
        if (!email || !password || !role) {
            return { valid: false, message: 'Заповніть всі поля' };
        }

        if (!Validators.isValidEmail(email)) {
            return { valid: false, message: 'Некоректний email' };
        }

        if (!Validators.isValidPassword(password)) {
            return { valid: false, message: 'Пароль повинен містити мінімум 8 символів' };
        }

        return { valid: true };
    }

    _validateEditUserForm({ email, password, role }) {
        if (!email || !role) {
            return { valid: false, message: 'Email та роль є обов\'язковими' };
        }

        if (!Validators.isValidEmail(email)) {
            return { valid: false, message: 'Некоректний email' };
        }

        if (password && !Validators.isValidPassword(password)) {
            return { valid: false, message: 'Пароль повинен містити мінімум 8 символів' };
        }

        return { valid: true };
    }

    async _loadCvatSettings() {
        try {
            const settings = await Auth.authenticatedRequest('/admin/cvat-settings');
            if (!settings) return;

            this.state.currentCvatSettings.length = 0;
            this.state.currentCvatSettings.push(...settings);

            this._renderCvatSettings();
        } catch (error) {
            console.error('Помилка завантаження налаштувань CVAT:', error);
            await showNotification('Помилка завантаження налаштувань CVAT', 'error');
        }
    }

    _renderCvatSettings() {
        const container = this.elements.cvat.settingsGrid;
        container.innerHTML = '';

        const projectNames = {
            'motion-det': 'Motion Detection',
            'tracking': 'Tracking & Re-identification',
            'mil-hardware': 'Mil Hardware Detection',
            're-id': 'Re-ID'
        };

        this.state.currentCvatSettings.forEach(setting => {
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

            card.addEventListener('click', (e) => this._handleCvatActions(e));
            container.appendChild(card);
        });
    }

    _handleCvatActions(e) {
        const action = e.target.dataset.action;
        const projectName = e.target.dataset.project;

        if (action === 'edit-cvat') {
            this._editCvatSettings(projectName);
        }
    }

    _editCvatSettings(projectName) {
        const setting = this.state.currentCvatSettings.find(s => s.project_name === projectName);
        if (!setting) return;

        this.state.currentEditingProject = projectName;

        const projectNames = {
            'motion-det': 'Motion Detection',
            'tracking': 'Tracking & Re-identification',
            'mil-hardware': 'Mil Hardware Detection',
            're-id': 'Re-ID'
        };

        this.elements.cvat.modalTitle.textContent = `Редагувати ${projectNames[projectName]}`;
        this.elements.cvat.projectId.value = setting.project_id;
        this.elements.cvat.overlap.value = setting.overlap;
        this.elements.cvat.segmentSize.value = setting.segment_size;
        this.elements.cvat.imageQuality.value = setting.image_quality;
        UI.clearFormErrors(this.elements.cvat.form);
        this.elements.cvat.modal.style.display = 'block';
    }

    async _handleSaveCvatSettings() {
        if (!this.state.currentEditingProject) return;

        const formData = {
            projectId: parseInt(this.elements.cvat.projectId.value),
            overlap: parseInt(this.elements.cvat.overlap.value),
            segmentSize: parseInt(this.elements.cvat.segmentSize.value),
            imageQuality: parseInt(this.elements.cvat.imageQuality.value)
        };

        const validation = this._validateCvatForm(formData);
        if (!validation.valid) {
            await showNotification(validation.message, 'error');
            return;
        }

        try {
            const data = await Auth.authenticatedRequest(`/admin/cvat-settings/${this.state.currentEditingProject}`, {
                method: 'PUT',
                body: JSON.stringify({
                    project_id: formData.projectId,
                    overlap: formData.overlap,
                    segment_size: formData.segmentSize,
                    image_quality: formData.imageQuality
                })
            });

            if (!data) return;

            await showNotification('Налаштування успішно збережені', 'success');
            this._closeCvatModal();
            await this._loadCvatSettings();
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'save CVAT settings');
            await showNotification(message, 'error');
        }
    }

    async _handleResetCvatSettings() {
        const confirmed = await showConfirm('Скинути всі налаштування CVAT до дефолтних значень?\n\nЦе оновить всі проєкти.');
        if (!confirmed) return;

        const defaultSettings = [
            { project_name: 'motion-det', project_id: 5, overlap: 5, segment_size: 400, image_quality: 100 },
            { project_name: 'tracking', project_id: 6, overlap: 5, segment_size: 400, image_quality: 100 },
            { project_name: 'mil-hardware', project_id: 7, overlap: 5, segment_size: 400, image_quality: 100 },
            { project_name: 're-id', project_id: 8, overlap: 5, segment_size: 400, image_quality: 100 }
        ];

        try {
            const updatePromises = defaultSettings.map(setting =>
                Auth.authenticatedRequest(`/admin/cvat-settings/${setting.project_name}`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        project_id: setting.project_id,
                        overlap: setting.overlap,
                        segment_size: setting.segment_size,
                        image_quality: setting.image_quality
                    })
                })
            );

            const responses = await Promise.all(updatePromises);

            const failedRequests = responses.filter(response => !response);
            if (failedRequests.length > 0) {
                throw new Error('Деякі налаштування не вдалося оновити');
            }

            await showNotification('Налаштування успішно скинуті до дефолтних значень', 'success');
            await this._loadCvatSettings();
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'reset CVAT settings');
            await showNotification(message, 'error');
        }
    }

    _validateCvatForm({ projectId, overlap, segmentSize, imageQuality }) {
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

    _getRoleDisplayName(role) {
        const roleNames = {
            'super_admin': 'Super Admin',
            'admin': 'Admin',
            'annotator': 'Annotator'
        };
        return roleNames[role] || role;
    }

    _closeUserModal() {
        this.elements.users.modal.style.display = 'none';
        this.elements.users.form.reset();
        UI.clearFormErrors(this.elements.users.form);
        this.state.currentEditingUser = null;
    }

    _closeEditUserModal() {
        this.elements.editUser.modal.style.display = 'none';
        this.elements.editUser.form.reset();
        UI.clearFormErrors(this.elements.editUser.form);
        this.state.currentEditingUser = null;
    }

    _closeCvatModal() {
        this.elements.cvat.modal.style.display = 'none';
        UI.clearFormErrors(this.elements.cvat.form);
        this.state.currentEditingProject = null;
    }

    _closeAllModals() {
        this._closeUserModal();
        this._closeEditUserModal();
        this._closeCvatModal();
    }

    _handleWindowClick(e) {
        if (e.target.classList.contains('modal')) {
            this._closeAllModals();
        }
    }
}

/**
 * Ініціалізація при завантаженні сторінки
 */
document.addEventListener('DOMContentLoaded', () => {
    window.adminPanel = new AdminPanel();
});