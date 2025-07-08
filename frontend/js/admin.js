class AdminPanel {
    constructor() {
        this.userModal = new BaseModal('user-modal', 'user-form');
        this.editModal = new BaseModal('edit-user-modal', 'edit-user-form');
        this.cvatModal = new BaseModal('cvat-modal', 'cvat-form');

        // Безпечна ініціалізація форм
        const userFormEl = document.getElementById('user-form');
        const editFormEl = document.getElementById('edit-user-form');
        const cvatFormEl = document.getElementById('cvat-form');

        this.userForm = userFormEl ? new BaseForm(userFormEl) : null;
        this.editForm = editFormEl ? new BaseForm(editFormEl) : null;
        this.cvatForm = cvatFormEl ? new BaseForm(cvatFormEl) : null;

        // Стан для пагінації відео
        this.videosCurrentPage = 1;
        this.videosPerPage = 20;

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
        document.querySelectorAll('.tab-button').forEach(btn =>
            btn.onclick = () => this.switchTab(btn.dataset.tab));

        const eventMappings = [
            ['#add-user-btn', () => this.userModal.open()],
            ['#save-user-btn', () => this.saveUser()],
            ['#cancel-user-btn', () => this.userModal.close()],
            ['#save-edit-user-btn', () => this.saveEditUser()],
            ['#cancel-edit-user-btn', () => this.editModal.close()],
            ['#save-cvat-btn', () => this.saveCvat()],
            ['#cancel-cvat-btn', () => this.cvatModal.close()],
            ['#reset-cvat-btn', () => this.resetCvatSettings()],
            ['#fix-orphaned-btn', () => this.fixOrphanedVideos()],
            ['#check-health-btn', () => this.checkSystemHealth()],
            ['#cleanup-locks-btn', () => this.cleanupLocks()],
            ['#force-cleanup-btn', () => this.forceCleanupLocks()]
        ];

        eventMappings.forEach(([selector, handler]) => {
            const element = document.querySelector(selector);
            if (element) {
                element.onclick = handler;
            } else {
                console.warn(`Element not found: ${selector}`);
            }
        });

        document.addEventListener('click', this.handleDelegatedClick.bind(this));
    }

    async switchTab(tabName) {
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

        const tabButton = document.querySelector(`[data-tab="${tabName}"]`);
        const tabContent = document.getElementById(`${tabName}-tab`);
        
        if (tabButton) {
            tabButton.classList.add('active');
        }
        
        if (tabContent) {
            tabContent.classList.add('active');
        }

        // Завантажуємо дані для відео при переключенні на вкладку
        if (tabName === 'videos') {
            await this.loadVideos();
        }
    }

    handleDelegatedClick(e) {
        const { action, userId, project, videoId } = e.target.dataset;
        const actions = {
            'edit-user': () => this.editUser(userId),
            'delete-user': () => this.deleteUser(userId),
            'edit-cvat': () => this.editCvat(project),
            'delete-video': () => this.deleteVideo(videoId)
        };
        actions[action]?.();
    }

    async loadData() {
        const [users, cvat] = await Promise.all([
            api.get('/admin/users'),
            api.get('/admin/cvat-settings')
        ]);

        this.renderUsers(users);
        this.renderUsersStats(users);
        this.renderCvat(cvat);

        // Завантажуємо відео тільки якщо потрібно (щоб не завантажувати завжди)
        const videosTab = document.getElementById('videos-tab');
        if (videosTab && videosTab.classList.contains('active')) {
            await this.loadVideos();
        }
    }

    renderUsersStats(users) {
        const total = users.length;
        const active = users.filter(u => u.is_active).length;
        const inactive = total - active;
        
        const totalElement = document.getElementById('users-total');
        const activeElement = document.getElementById('users-active');
        const inactiveElement = document.getElementById('users-inactive');
        
        if (totalElement) {
            totalElement.textContent = total;
        }
        if (activeElement) {
            activeElement.textContent = active;
        }
        if (inactiveElement) {
            inactiveElement.textContent = inactive;
        }
    }

    renderUsers(users) {
        const currentUserRole = auth.role;
        const usersTableBody = document.querySelector('#users-table tbody');
        
        if (!usersTableBody) {
            console.warn('Users table body not found');
            return;
        }
        
        usersTableBody.innerHTML = users.map(user => {
            // Логіка для показу кнопок редагування та видалення
            let actionButtons = '';
            
            // Супер адміни не можуть редагувати/видаляти один одного
            const canEdit = !(currentUserRole === 'super_admin' && user.role === 'super_admin');
            
            if (canEdit) {
                actionButtons = `
                    <button class="btn btn-icon" data-action="edit-user" data-user-id="${user.id}">✏️</button>
                    <button class="btn btn-danger btn-icon" data-action="delete-user" data-user-id="${user.id}">🗑️</button>
                `;
            } else {
                actionButtons = '<span class="text-muted">—</span>';
            }
            
            return `
            <tr>
                <td>${utils.escapeHtml(user.email)}</td>
                <td><span class="role-badge ${user.role}">${user.role}</span></td>
                <td><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">
                    ${user.is_active ? 'Активний' : 'Неактивний'}</span></td>
                <td>${new Date(user.created_at_utc).toLocaleDateString()}</td>
                <td>${actionButtons}</td>
            </tr>
            `;
        }).join('');
    }

    renderCvat(settings) {
        const names = {
            'motion_detection': 'Motion Detection',
            'military_targets_detection_and_tracking_moving': 'Military Targets Moving',
            'military_targets_detection_and_tracking_static': 'Military Targets Static',
            're_id': 'Re-identification'
        };

        const cvatGrid = document.getElementById('cvat-settings-grid');
        
        if (!cvatGrid) {
            console.warn('CVAT settings grid not found');
            return;
        }

        cvatGrid.innerHTML = settings.map(s => `
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
                    <div class="setting-item">
                        <span class="setting-label">Segment Size:</span>
                        <span class="setting-value">${s.segment_size}</span>
                    </div>
                    <div class="setting-item">
                        <span class="setting-label">Image Quality:</span>
                        <span class="setting-value">${s.image_quality}%</span>
                    </div>
                </div>
            </div>
        `).join('');
    }

    async saveUser() {
        if (!this.userForm) {
            notify('Форма користувача не знайдена', 'error');
            return;
        }

        const rules = {
            email: { required: true, validator: validators.email, message: 'Некоректний email' },
            password: { required: true, validator: validators.password, message: 'Мінімум 8 символів' },
            role: { required: true }
        };

        if (!this.userForm.validate(rules)) return;

        try {
            const response = await api.post('/admin/users', this.userForm.getData());
            if (response.success) {
                notify('Користувача створено', 'success');
                this.userModal.close();
                this.loadData();
            } else {
                notify(response.message || 'Помилка', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async deleteUser(userId) {
        if (!await confirm('Видалити користувача?')) return;

        try {
            const response = await api.delete(`/admin/users/${userId}`);
            if (response.success) {
                notify('Користувача видалено', 'success');
                this.loadData();
            } else {
                notify(response.message || 'Помилка', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async editUser(userId) {
        try {
            const users = await api.get('/admin/users');
            const user = users.find(u => u.id === userId);

            const emailField = document.getElementById('edit-user-email');
            const roleField = document.getElementById('edit-user-role');
            
            if (emailField) emailField.value = user.email;
            if (roleField) roleField.value = user.role;
            
            this.editModal.currentUserId = userId;
            this.editModal.open();
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async saveEditUser() {
        if (!this.editForm) {
            notify('Форма редагування не знайдена', 'error');
            return;
        }

        const data = this.editForm.getData();
        if (!data.email) return;

        try {
            const response = await api.put(`/admin/users/${this.editModal.currentUserId}`, data);
            if (response.success) {
                notify('Користувача оновлено', 'success');
                this.editModal.close();
                this.loadData();
            } else {
                notify(response.message || 'Помилка', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async editCvat(project) {
        try {
            const settings = await api.get('/admin/cvat-settings');
            const setting = settings.find(s => s.project_name === project);

            const fieldMappings = {
                'project-id': 'project_id',
                'overlap': 'overlap',
                'segment-size': 'segment_size',
                'image-quality': 'image_quality'
            };

            Object.entries(fieldMappings).forEach(([fieldId, key]) => {
                const input = document.getElementById(`cvat-${fieldId}`);
                if (input) input.value = setting[key];
            });

            // Update project ID hint with general validation info
            const hintElement = document.getElementById('project-id-hint');
            if (hintElement) {
                hintElement.textContent = 'ID повинен бути унікальним та від 1 до 1000';
            }

            this.cvatModal.currentProject = project;
            this.cvatModal.clearErrors(); // Очищаємо попередні помилки
            this.cvatModal.open();
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async saveCvat() {
        if (!this.cvatForm) {
            notify('Форма CVAT не знайдена', 'error');
            return;
        }

        const data = this.cvatForm.getData();

        // Валідація полів на фронтенді
        const validationRules = {
            projectId: { 
                required: true, 
                validator: (v) => v >= 1 && v <= 1000, 
                message: 'Project ID повинен бути від 1 до 1000' 
            },
            overlap: { 
                required: true, 
                validator: (v) => v >= 0 && v <= 100, 
                message: 'Overlap повинен бути від 0 до 100%' 
            },
            segmentSize: { 
                required: true, 
                validator: (v) => v >= 50 && v <= 2000, 
                message: 'Segment Size повинен бути від 50 до 2000' 
            },
            imageQuality: { 
                required: true, 
                validator: (v) => v >= 1 && v <= 100, 
                message: 'Image Quality повинна бути від 1 до 100%' 
            }
        };

        if (!this.cvatForm.validate(validationRules)) {
            return;
        }

        const projectId = +data.projectId;

        try {
            const response = await api.put(`/admin/cvat-settings/${this.cvatModal.currentProject}`, {
                project_name: this.cvatModal.currentProject,
                project_id: projectId,
                overlap: +data.overlap,
                segment_size: +data.segmentSize,
                image_quality: +data.imageQuality
            });

            if (response.success) {
                notify('Налаштування збережено', 'success');
                this.cvatModal.close();
                this.loadData();
            } else {
                notify(response.message || 'Помилка', 'error');
            }
        } catch (e) {
            // Показуємо детальну інформацію про помилку
            let errorMessage = e.message;
            
            // Якщо це помилка валідації, показуємо кожне поле окремо
            if (errorMessage.includes('Деталі:')) {
                const [mainMsg, details] = errorMessage.split('. Деталі: ');
                errorMessage = `${mainMsg}\n\nДеталі помилок:\n${details.split('; ').join('\n')}`;
            }
            
            notify(errorMessage, 'error');
        }
    }

    async resetCvatSettings() {
        if (!await confirm('Скинути всі CVAT налаштування до дефолтних значень? Ця дія незворотна.')) {
            return;
        }

        try {
            const response = await api.post('/admin/reset-cvat-settings');
            
            if (response.success) {
                notify('CVAT налаштування скинуті до дефолтних значень', 'success');
                this.loadData(); // Перезавантажуємо дані
            } else {
                notify(response.message || 'Помилка скидання налаштувань', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async loadVideos() {
        try {
            const response = await api.get(`/admin/videos?page=${this.videosCurrentPage}&per_page=${this.videosPerPage}`);
            if (response.success) {
                this.renderVideos(response.videos);
                this.renderVideosPagination(response.pagination);
                this.renderVideosStats(response.videos);
            } else {
                notify(response.error || 'Помилка завантаження відео', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    renderVideos(videos) {
        const tbody = document.querySelector('#videos-table tbody');
        
        if (!tbody) {
            console.warn('Videos table body not found');
            return;
        }
        
        tbody.innerHTML = videos.map(video => {
            const statusClass = this.getVideoStatusClass(video.status);
            const lockInfo = video.lock_status.locked 
                ? `🔒 ${video.lock_status.locked_by}` 
                : '🔓 Вільне';
            
            const duration = video.duration_sec 
                ? `${Math.floor(video.duration_sec / 60)}:${(video.duration_sec % 60).toString().padStart(2, '0')}`
                : '-';
            
            const size = video.size_mb ? `${video.size_mb} MB` : '-';
            
            return `
                <tr>
                    <td class="filename-cell" title="${utils.escapeHtml(video.filename)}">
                        ${utils.escapeHtml(video.filename)}
                    </td>
                    <td><span class="status-badge ${statusClass}">${this.getVideoStatusText(video.status)}</span></td>
                    <td>${size}</td>
                    <td>${duration}</td>
                    <td>${new Date(video.created_at).toLocaleDateString()}</td>
                    <td>
                        <span class="file-status ${video.local_file_exists ? 'exists' : 'missing'}">
                            ${video.local_file_exists ? '✅ Є' : '❌ Відсутній'}
                        </span>
                    </td>
                    <td class="lock-cell">${lockInfo}</td>
                    <td>
                        <button class="btn btn-danger btn-icon" 
                                data-action="delete-video" 
                                data-video-id="${video.id}"
                                title="Видалити відео">🗑️</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    renderVideosPagination(pagination) {
        const container = document.getElementById('videos-pagination');
        
        if (!container) {
            console.warn('Videos pagination container not found');
            return;
        }
        
        if (pagination.total_pages <= 1) {
            container.innerHTML = '';
            return;
        }

        const buttons = [];
        
        // Кнопка "Попередня"
        if (pagination.has_prev) {
            buttons.push(`<button class="btn btn-secondary" onclick="adminPanel.changeVideosPage(${pagination.current_page - 1})">Попередня</button>`);
        }

        // Номери сторінок
        for (let i = 1; i <= pagination.total_pages; i++) {
            const active = i === pagination.current_page ? 'btn-primary' : 'btn-secondary';
            buttons.push(`<button class="btn ${active}" onclick="adminPanel.changeVideosPage(${i})">${i}</button>`);
        }

        // Кнопка "Наступна"
        if (pagination.has_next) {
            buttons.push(`<button class="btn btn-secondary" onclick="adminPanel.changeVideosPage(${pagination.current_page + 1})">Наступна</button>`);
        }

        container.innerHTML = `
            <div class="pagination">
                ${buttons.join('')}
            </div>
            <div class="pagination-info">
                Сторінка ${pagination.current_page} з ${pagination.total_pages} 
                (всього: ${pagination.total_count} відео)
            </div>
        `;
    }

    renderVideosStats(videos) {
        const total = videos.length;
        const withFiles = videos.filter(v => v.local_file_exists).length;
        
        const totalElement = document.getElementById('videos-total');
        const withFilesElement = document.getElementById('videos-with-files');
        
        if (totalElement) {
            totalElement.textContent = total;
        }
        
        if (withFilesElement) {
            withFilesElement.textContent = withFiles;
        }
    }

    async changeVideosPage(page) {
        this.videosCurrentPage = page;
        await this.loadVideos();
    }

    getVideoStatusClass(status) {
        const statusClasses = {
            'not_annotated': 'ready',
            'in_progress': 'progress',
            'annotated': 'completed',
            'processing_clips': 'processing',
            'downloading': 'downloading',
            'download_error': 'error'
        };
        return statusClasses[status] || 'unknown';
    }

    getVideoStatusText(status) {
        const statusTexts = {
            'not_annotated': 'Готове для анотації',
            'in_progress': 'В процесі анотації',
            'annotated': 'Анотоване',
            'processing_clips': 'Обробляються кліпи',
            'downloading': 'Завантажується',
            'download_error': 'Помилка завантаження'
        };
        return statusTexts[status] || status;
    }

    async deleteVideo(videoId) {
        if (!await confirm('Видалити відео? Це видалить локальний файл та всі дані з бази.')) {
            return;
        }

        try {
            const response = await api.delete(`/admin/videos/${videoId}`);
            if (response.success) {
                notify(response.message || 'Відео успішно видалено', 'success');
                await this.loadVideos(); // Перезавантажуємо список
            } else {
                notify(response.error || 'Помилка видалення відео', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async fixOrphanedVideos() {
        if (!await confirm('Виправити завислі відео зі статусом "В процесі анотації", які не заблоковані?')) {
            return;
        }

        try {
            const response = await api.post('/admin/fix-orphaned-videos');
            if (response.success) {
                notify(response.message || 'Завислі відео виправлено', 'success');
                await this.loadVideos(); // Перезавантажуємо список
            } else {
                notify(response.error || 'Помилка виправлення відео', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async checkSystemHealth() {
        const healthBtn = document.getElementById('check-health-btn');
        const healthInfo = document.getElementById('health-info');
        
        try {
            if (healthBtn) {
                healthBtn.disabled = true;
                healthBtn.textContent = 'Перевіряю...';
            }
            
            const healthData = await api.get('/admin/system-health');
            this.renderHealthInfo(healthData);
            
        } catch (e) {
            notify(e.message, 'error');
            if (healthInfo) {
                healthInfo.innerHTML = `
                    <div class="health-section">
                        <div class="health-status error">❌ Помилка отримання інформації</div>
                        <div class="health-details">${utils.escapeHtml(e.message)}</div>
                    </div>
                `;
            }
        } finally {
            if (healthBtn) {
                healthBtn.disabled = false;
                healthBtn.textContent = 'Перевірити стан';
            }
        }
    }

    async cleanupLocks() {
        try {
            const response = await api.post('/admin/cleanup-locks');
            if (response.success) {
                notify(response.message, 'success');
                // Refresh health info if it's visible
                this.checkSystemHealth();
            } else {
                notify(response.error || 'Помилка', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    async forceCleanupLocks() {
        const confirmed = await confirm(
            'УВАГА! Це видалить ВСІ блокування відео, включно з активними. ' +
            'Користувачі можуть втратити поточний прогрес. Продовжити?'
        );
        
        if (!confirmed) return;

        try {
            const response = await api.post('/admin/force-cleanup-locks');
            if (response.success) {
                notify(response.message, 'warning');
                // Refresh health info
                this.checkSystemHealth();
            } else {
                notify(response.error || 'Помилка', 'error');
            }
        } catch (e) {
            notify(e.message, 'error');
        }
    }

    renderHealthInfo(healthInfo) {
        const container = document.getElementById('health-info');
        
        if (!container) {
            console.warn('Health info container not found');
            return;
        }
        
        let html = `<div class="health-grid">`;
        
        // Redis section
        html += this.renderHealthSection('Redis', healthInfo.redis, {
            'З\'єднання': healthInfo.redis.redis_connected ? '✅ Підключено' : '❌ Відключено',
            'Використана пам\'ять': healthInfo.redis.redis_memory_used || 'N/A',
            'Час роботи': this.formatUptime(healthInfo.redis.redis_uptime || 0),
            'Всього блокувань': healthInfo.redis.total_video_locks || 0,
            'Прострочені блокування': healthInfo.redis.expired_locks_without_ttl || 0
        });
        
        // MongoDB section  
        html += this.renderHealthSection('MongoDB', healthInfo.mongodb, {
            'З\'єднання': healthInfo.mongodb.connected ? '✅ Підключено' : '❌ Відключено',
            'Користувачі': healthInfo.mongodb.total_users || 0,
            'Відео': healthInfo.mongodb.total_videos || 0
        });
        
        // Users section
        if (healthInfo.users && !healthInfo.users.error) {
            html += this.renderHealthSection('Користувачі', healthInfo.users, {
                'Всього': healthInfo.users.total || 0,
                'Активні': healthInfo.users.active || 0,
                'Неактивні': healthInfo.users.inactive || 0,
                'Супер адміни': healthInfo.users.by_role?.super_admin || 0,
                'Адміни': healthInfo.users.by_role?.admin || 0,
                'Анотатори': healthInfo.users.by_role?.annotator || 0
            });
        }
        
        // Videos section
        if (healthInfo.videos && !healthInfo.videos.error) {
            html += this.renderHealthSection('Відео', healthInfo.videos, {
                'Всього': healthInfo.videos.total || 0,
                ...healthInfo.videos.by_status
            });
        }
        
        html += `</div>`;
        
        // Add detailed Redis locks info if available
        if (healthInfo.redis.locks_detail && healthInfo.redis.locks_detail.length > 0) {
            html += `
                <div class="health-section">
                    <h3>Активні блокування (перші 10)</h3>
                    <div class="health-details">
                        ${healthInfo.redis.locks_detail.map(lock => `
                            <div style="margin-bottom: 8px;">
                                <strong>${lock.key}</strong> - ${lock.user_email}<br>
                                TTL: ${lock.ttl}s, Заблоковано: ${new Date(lock.locked_at).toLocaleString()}
                                ${lock.expired ? ' <span style="color: #ef4444;">(ПРОСТРОЧЕНО)</span>' : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        html += `<p style="margin-top: 20px; color: var(--text-muted); font-size: 0.9em;">
            Останнє оновлення: ${new Date(healthInfo.timestamp).toLocaleString()}
        </p>`;
        
        container.innerHTML = html;
    }

    renderHealthSection(title, sectionData, items) {
        const hasError = sectionData.error;
        const statusClass = hasError ? 'error' : 'healthy';
        const statusIcon = hasError ? '❌' : '✅';
        
        let html = `
            <div class="health-section">
                <h3>${title}</h3>
                <div class="health-status ${statusClass}">
                    ${statusIcon} ${hasError ? 'Помилка' : 'OK'}
                </div>
        `;
        
        if (hasError) {
            html += `<div class="health-details">${utils.escapeHtml(sectionData.error)}</div>`;
        } else {
            html += `<div class="health-grid">`;
            Object.entries(items).forEach(([label, value]) => {
                html += `
                    <div class="health-item">
                        <div class="health-item-label">${label}</div>
                        <div class="health-item-value">${value}</div>
                    </div>
                `;
            });
            html += `</div>`;
        }
        
        html += `</div>`;
        return html;
    }

    formatUptime(seconds) {
        if (!seconds) return '0s';
        
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        const parts = [];
        if (days > 0) parts.push(`${days}д`);
        if (hours > 0) parts.push(`${hours}г`);
        if (minutes > 0) parts.push(`${minutes}хв`);
        
        return parts.length > 0 ? parts.join(' ') : `${seconds}с`;
    }
}

// Глобальна змінна для доступу до методів пагінації
let adminPanel;

document.addEventListener('DOMContentLoaded', () => {
    adminPanel = new AdminPanel();
});