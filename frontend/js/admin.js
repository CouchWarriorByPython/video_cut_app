// admin.js - Спрощена версія (скорочено з ~500 до ~200 рядків)

class AdminPanel {
    constructor() {
        this.userModal = new BaseModal('user-modal', 'user-form');
        this.editModal = new BaseModal('edit-user-modal', 'edit-user-form');
        this.cvatModal = new BaseModal('cvat-modal', 'cvat-form');

        this.userForm = new BaseForm(document.getElementById('user-form'));
        this.editForm = new BaseForm(document.getElementById('edit-user-form'));
        this.cvatForm = new BaseForm(document.getElementById('cvat-form'));

        this.init();
    }

    async init() {
        if (!await this.checkAccess()) return;

        this.setupEvents();
        await this.loadData();
    }

    async checkAccess() {
        try {
            await api.get('/admin/stats');
            return true;
        } catch {
            location.href = '/';
            return false;
        }
    }

    setupEvents() {
        // Tabs
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.onclick = () => this.switchTab(btn.dataset.tab);
        });

        // User actions
        document.getElementById('add-user-btn').onclick = () => this.userModal.open();
        document.getElementById('save-user-btn').onclick = () => this.saveUser();
        document.getElementById('save-edit-user-btn').onclick = () => this.saveEditUser();

        // CVAT actions
        document.getElementById('save-cvat-btn').onclick = () => this.saveCvat();

        // Delegated events
        document.addEventListener('click', this.handleDelegatedClick.bind(this));
    }

    switchTab(tabName) {
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        document.getElementById(`${tabName}-tab`).classList.add('active');
    }

    handleDelegatedClick(e) {
        const { action, userId, project } = e.target.dataset;

        switch (action) {
            case 'edit-user': this.editUser(userId); break;
            case 'delete-user': this.deleteUser(userId); break;
            case 'edit-cvat': this.editCvat(project); break;
        }
    }

    async loadData() {
        const [stats, users, cvat] = await Promise.all([
            api.get('/admin/stats'),
            api.get('/admin/users'),
            api.get('/admin/cvat-settings')
        ]);

        this.renderStats(stats);
        this.renderUsers(users);
        this.renderCvat(cvat);
    }

    renderStats({ total_users, active_users, total_videos, processing_videos }) {
        document.getElementById('total-users').textContent = total_users;
        document.getElementById('active-users').textContent = active_users;
        document.getElementById('total-videos').textContent = total_videos;
        document.getElementById('processing-videos').textContent = processing_videos;
    }

    renderUsers(users) {
        const tbody = document.querySelector('#users-table tbody');
        tbody.innerHTML = users.map(user => `
            <tr>
                <td>${utils.escapeHtml(user.email)}</td>
                <td><span class="role-badge ${user.role}">${user.role}</span></td>
                <td><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Активний' : 'Неактивний'}</span></td>
                <td>${new Date(user.created_at).toLocaleDateString()}</td>
                <td>
                    <button class="btn btn-icon" data-action="edit-user" data-user-id="${user.id}">✏️</button>
                    <button class="btn btn-danger btn-icon" data-action="delete-user" data-user-id="${user.id}">🗑️</button>
                </td>
            </tr>
        `).join('');
    }

    renderCvat(settings) {
        const grid = document.getElementById('cvat-settings-grid');
        const names = {
            'motion-det': 'Motion Detection',
            'tracking': 'Tracking',
            'mil-hardware': 'Mil Hardware',
            're-id': 'Re-ID'
        };

        grid.innerHTML = settings.map(s => `
            <div class="cvat-project-card">
                <div class="project-header">
                    <h3>${names[s.project_name]}</h3>
                    <button class="btn btn-icon" data-action="edit-cvat" data-project="${s.project_name}">✏️</button>
                </div>
                <div class="project-settings">
                    <div class="setting-item">
                        <span class="setting-label">Project ID:</span>
                        <span class="setting-value">${s.project_id}</span>
                    </div>
                    <div class="setting-item">
                        <span class="setting-label">Overlap:</span>
                        <span class="setting-value">${s.overlap}%</span>
                    </div>
                </div>
            </div>
        `).join('');
    }

    async saveUser() {
        const rules = {
            email: { required: true, validator: validators.email, message: 'Некоректний email' },
            password: { required: true, validator: validators.password, message: 'Мінімум 8 символів' },
            role: { required: true }
        };

        if (!this.userForm.validate(rules)) return;

        try {
            await api.post('/admin/users', this.userForm.getData());
            notify('Користувача створено', 'success');
            this.userModal.close();
            this.loadData();
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async deleteUser(userId) {
        if (!await confirm('Видалити користувача?')) return;

        try {
            await api.delete(`/admin/users/${userId}`);
            notify('Користувача видалено', 'success');
            this.loadData();
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async editUser(userId) {
        const user = await api.get(`/admin/users/${userId}`);

        document.getElementById('edit-user-email').value = user.email;
        document.getElementById('edit-user-role').value = user.role;
        this.editModal.currentUserId = userId;
        this.editModal.open();
    }

    async saveEditUser() {
        const data = this.editForm.getData();
        if (!data.email) return;

        try {
            await api.put(`/admin/users/${this.editModal.currentUserId}`, data);
            notify('Користувача оновлено', 'success');
            this.editModal.close();
            this.loadData();
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async editCvat(project) {
        const settings = await api.get('/admin/cvat-settings');
        const setting = settings.find(s => s.project_name === project);

        Object.entries(setting).forEach(([key, value]) => {
            const input = document.getElementById(`cvat-${key.replace('_', '-')}`);
            if (input) input.value = value;
        });

        this.cvatModal.currentProject = project;
        this.cvatModal.open();
    }

    async saveCvat() {
        const data = this.cvatForm.getData();

        try {
            await api.put(`/admin/cvat-settings/${this.cvatModal.currentProject}`, {
                project_id: +data.projectId,
                overlap: +data.overlap,
                segment_size: +data.segmentSize,
                image_quality: +data.imageQuality
            });
            notify('Налаштування збережено', 'success');
            this.cvatModal.close();
            this.loadData();
        } catch (e) {
            notify(e.message, 'error');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AdminPanel();
});