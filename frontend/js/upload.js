class VideoUploader {
    constructor() {
        this.elements = {
            videoUrl: document.getElementById('video-url'),
            downloadAllFolder: document.getElementById('download-all-folder'),
            uploadBtn: document.getElementById('upload-btn'),
            result: document.getElementById('result')
        };
        this.activeUploads = new Map();
        this.progressIntervals = new Map();
        this._init();
    }

    _init() {
        this._setupEventListeners();
        this._loadSavedUploads();
    }

    _setupEventListeners() {
        this.elements.uploadBtn.addEventListener('click', () => this._handleUpload());
        this.elements.videoUrl.addEventListener('input', utils.debounce(() => this._validateUrls(), 300));
        this.elements.downloadAllFolder.addEventListener('change', () => this._handleFolderCheckboxChange());
    }

    _handleFolderCheckboxChange() {
        const isChecked = this.elements.downloadAllFolder.checked;
        if (isChecked) {
            this.elements.videoUrl.placeholder = "https://storage-account.blob.core.windows.net/container/folder/";
            this.elements.videoUrl.rows = 1;
        } else {
            this.elements.videoUrl.placeholder = "https://storage-account.blob.core.windows.net/container/path/video.mp4\nабо декілька URL через кому";
            this.elements.videoUrl.rows = 3;
        }
    }

    async _handleUpload() {
        const formData = this._getFormData();
        if (!this._validateForm(formData)) return;

        this._setButtonLoading(true);

        try {
            const data = await api.post('/video/upload', formData);
            if (data && data.success) {
                this._handleUploadResponse(data);
                this._resetForm();
            }
        } catch (error) {
            await notify(error.message, 'error');
        } finally {
            this._setButtonLoading(false);
        }
    }

    _getFormData() {
        const urlsText = this.elements.videoUrl.value.trim();
        const urls = this.elements.downloadAllFolder.checked ?
            [urlsText] :
            urlsText.split(',').map(url => url.trim()).filter(url => url);

        return {
            video_urls: urls,
            download_all_folder: this.elements.downloadAllFolder.checked
        };
    }

    _validateForm(data) {
        const errors = [];

        if (!data.video_urls.length) {
            errors.push('Необхідно вказати хоча б один URL');
        }

        if (data.download_all_folder && data.video_urls.length > 1) {
            errors.push('При завантаженні папки можна вказати тільки один URL');
        }

        data.video_urls.forEach((url, index) => {
            if (data.download_all_folder) {
                if (!validators.azureFolderUrl(url) && !validators.azureUrl(url)) {
                    errors.push('URL папки має бути з Azure Blob Storage');
                }
            } else {
                if (!validators.azureUrl(url)) {
                    errors.push(`URL #${index + 1} некоректний`);
                }
                if (!['.mp4', '.avi', '.mov', '.mkv'].some(ext => url.toLowerCase().includes(ext))) {
                    errors.push(`URL #${index + 1} має містити відео файл`);
                }
            }
        });

        if (errors.length > 0) {
            notify(errors.join('\n'), 'error');
            return false;
        }
        return true;
    }

    _validateUrls() {
        const urls = this.elements.videoUrl.value.trim();
        if (urls) {
            const urlList = this.elements.downloadAllFolder.checked ?
                [urls] :
                urls.split(',').map(url => url.trim());

            const allValid = urlList.every(url =>
                this.elements.downloadAllFolder.checked ?
                    url.includes('.blob.core.windows.net') :
                    validators.azureUrl(url)
            );

            this.elements.videoUrl.style.borderColor = allValid ? '' : '#e74c3c';
        }
    }

    _handleUploadResponse(data) {
        if (data.batch_results) {
            this._handleBatchResponse(data);
        } else {
            this._handleSingleResponse(data);
        }
        this._saveUploadsToStorage();
    }

    _handleBatchResponse(data) {
        const { successful, errors, info } = data.batch_results;
        
        this._showDetailedInfo(data, successful, errors, info);

        if (successful && successful.length > 0) {
            this._createBatchProgressDisplay(successful, data.message);
            successful.forEach(task => {
                if (task.task_id) {
                    const uploadData = {
                        id: utils.generateId(),
                        taskId: task.task_id,
                        filename: task.filename,
                        message: data.message,
                        timestamp: Date.now()
                    };
                    this.activeUploads.set(uploadData.id, uploadData);
                    this._showProgressBar(uploadData);
                    this._startProgressTracking(uploadData.id);
                }
            });
        }
    }

    _handleSingleResponse(data) {
        if (data.message.includes('вже існує') || data.message.includes('готове для анотації') || 
            data.message.includes('перезавантажується')) {
            this._showSingleVideoInfo(data);
            
            if (data.conversion_task_id) {
                const uploadData = {
                    id: utils.generateId(),
                    taskId: data.conversion_task_id,
                    azure_file_path: data.azure_file_path,
                    filename: data.filename,
                    message: data.message,
                    timestamp: Date.now()
                };
                this.activeUploads.set(uploadData.id, uploadData);
                this._showProgressBar(uploadData);
                this._startProgressTracking(uploadData.id);
            }
        } else {
            const uploadData = {
                id: utils.generateId(),
                taskId: data.conversion_task_id,
                azure_file_path: data.azure_file_path,
                filename: data.filename,
                message: data.message,
                timestamp: Date.now()
            };
            this.activeUploads.set(uploadData.id, uploadData);
            this._showProgressBar(uploadData);
            this._startProgressTracking(uploadData.id);
        }
    }

    _showDetailedInfo(data, successful, errors, info) {
        const sections = [];

        if (info?.existing_ready && info.existing_ready.length > 0) {
            sections.push({
                type: 'success',
                title: 'Відео готові для анотації',
                icon: '✓',
                files: info.existing_ready.map(v => ({
                    name: v.filename,
                    status: this._getStatusLabel(v.status),
                    type: 'ready'
                }))
            });
        }

        if (info?.redownloading && info.redownloading.length > 0) {
            sections.push({
                type: 'info',
                title: 'Перезавантажуються (відсутні локально)',
                icon: '↻',
                files: info.redownloading.map(v => ({
                    name: v.filename,
                    status: 'Завантажується заново',
                    type: 'downloading'
                }))
            });
        }

        if (successful && successful.length > 0) {
            const newDownloads = successful.filter(v => v.task_id);
            if (newDownloads.length > 0) {
                sections.push({
                    type: 'info',
                    title: 'Нові завантаження',
                    icon: '⬇',
                    files: newDownloads.map(v => ({
                        name: v.filename,
                        status: 'Додано в чергу завантаження',
                        type: 'downloading'
                    }))
                });
            }
        }

        if (errors && errors.length > 0) {
            sections.push({
                type: 'error', 
                title: 'Помилки',
                icon: '✗',
                files: errors.map(e => ({
                    name: this._extractFilenameFromUrl(e.url),
                    status: e.error,
                    type: 'error'
                }))
            });
        }

        this._showInfoModal(sections, data.message);
    }

    _showSingleVideoInfo(data) {
        const sections = [];
        
        if (data.message.includes('готове для анотації') || data.message.includes('вже існує')) {
            sections.push({
                type: 'success',
                title: 'Відео готове',
                icon: '✓',
                files: [{
                    name: data.filename,
                    status: 'Готове для анотації',
                    type: 'ready'
                }]
            });
        } else if (data.message.includes('перезавантажується')) {
            sections.push({
                type: 'info',
                title: 'Перезавантаження',
                icon: '↻',
                files: [{
                    name: data.filename,
                    status: 'Відсутнє локально, перезавантажується',
                    type: 'downloading'
                }]
            });
        }

        this._showInfoModal(sections, data.message);
    }

    _showInfoModal(sections, title) {
        const modal = document.createElement('div');
        modal.className = 'info-modal';
        
        const content = document.createElement('div');
        content.className = 'info-modal-content';
        
        const header = `
            <div class="info-modal-header">
                <h3 class="info-modal-title">${utils.escapeHtml(title)}</h3>
                <button class="info-modal-close">&times;</button>
            </div>
        `;
        
        const sectionsHTML = sections.map(section => `
            <div class="info-section">
                <div class="info-section-title">
                    <span class="info-section-icon ${section.type}">${section.icon}</span>
                    ${section.title}
                </div>
                <ul class="file-list">
                    ${section.files.map(file => `
                        <li class="file-item">
                            <span class="file-icon ${file.type}">
                                ${file.type === 'ready' ? '✓' : 
                                  file.type === 'downloading' ? '⬇' : '✗'}
                            </span>
                            <div class="file-info">
                                <div class="file-name">${utils.escapeHtml(file.name)}</div>
                                <div class="file-status ${file.type}">${utils.escapeHtml(file.status)}</div>
                            </div>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `).join('');
        
        const actions = `
            <div class="modal-actions">
                <button class="btn btn-primary modal-close-btn">Зрозуміло</button>
            </div>
        `;
        
        content.innerHTML = header + sectionsHTML + actions;
        modal.appendChild(content);
        document.body.appendChild(modal);
        
        const closeModal = () => {
            modal.remove();
        };
        
        content.querySelector('.info-modal-close').addEventListener('click', closeModal);
        content.querySelector('.modal-close-btn').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
        
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', handleEsc);
            }
        };
        document.addEventListener('keydown', handleEsc);
    }

    _createBatchProgressDisplay(tasks, message) {
        const total = tasks.length;
        let completed = 0;
        
        const progressId = utils.generateId();
        const progressHTML = `
            <div id="batch-progress-${progressId}" class="batch-progress">
                <div class="batch-progress-header">
                    <span class="batch-progress-title">Пакетне завантаження</span>
                    <span class="batch-progress-summary">0/${total}</span>
                </div>
                <div class="batch-progress-bar">
                    <div class="batch-progress-fill" style="width: 0%"></div>
                </div>
                <div class="batch-progress-details">${utils.escapeHtml(message)}</div>
            </div>
        `;
        
        this.elements.result.insertAdjacentHTML('afterbegin', progressHTML);
        this.elements.result.classList.remove('hidden');
        
        const updateBatchProgress = () => {
            const activeCount = Array.from(this.activeUploads.values())
                .filter(upload => tasks.some(task => task.task_id === upload.taskId)).length;
            
            completed = total - activeCount;
            const percentage = Math.round((completed / total) * 100);
            
            const element = document.getElementById(`batch-progress-${progressId}`);
            if (element) {
                element.querySelector('.batch-progress-summary').textContent = `${completed}/${total}`;
                element.querySelector('.batch-progress-fill').style.width = `${percentage}%`;
                
                if (completed === total) {
                    setTimeout(() => element.remove(), 3000);
                }
            }
        };
        
        const interval = setInterval(() => {
            updateBatchProgress();
            if (completed === total) {
                clearInterval(interval);
            }
        }, 5000);
    }

    _extractFilenameFromUrl(url) {
        try {
            const urlParts = url.split('/');
            return urlParts[urlParts.length - 1];
        } catch {
            return url;
        }
    }

    _getStatusLabel(status) {
        const labels = {
            'not_annotated': 'готове для анотації',
            'in_progress': 'в процесі анотації',
            'annotated': 'вже анотоване',
            'processing_clips': 'обробляються кліпи'
        };
        return labels[status] || status;
    }

    _showProgressBar(uploadData) {
        const azureUrl = uploadData.azure_file_path ?
            utils.azureFilePathToUrl(uploadData.azure_file_path) :
            uploadData.filename;

        const progressHTML = `
            <div id="progress-${uploadData.id}" class="upload-progress-item">
                <div class="upload-info">
                    <h3>Обробка відео</h3>
                    <p><strong>Файл:</strong> ${utils.escapeHtml(uploadData.filename)}</p>
                    ${uploadData.azure_file_path ? `
                        <p><strong>Azure посилання:</strong></p>
                        <p class="url-display">${utils.escapeHtml(azureUrl)}</p>
                    ` : ''}
                </div>
                <div class="progress-container">
                    <div class="progress-status">
                        <span class="status-text">Ініціалізація...</span>
                        <span class="progress-percentage">0%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" data-stage="queued" style="width: 0%"></div>
                    </div>
                    <div class="progress-stage">Чекаємо початку обробки...</div>
                </div>
                <div class="upload-actions">
                    <button class="btn btn-secondary" onclick="videoUploader.removeUpload('${uploadData.id}')">Приховати</button>
                </div>
            </div>
        `;

        this.elements.result.insertAdjacentHTML('afterbegin', progressHTML);
        this.elements.result.classList.remove('hidden');
    }

    _startProgressTracking(uploadId) {
        const interval = setInterval(() => this._checkTaskProgress(uploadId), 5000);
        this.progressIntervals.set(uploadId, interval);
    }

    async _checkTaskProgress(uploadId) {
        const uploadData = this.activeUploads.get(uploadId);
        if (!uploadData) return this._clearProgressInterval(uploadId);

        try {
            const data = await api.get(`/video/task/${uploadData.taskId}/status`);
            if (!data) return this.removeUpload(uploadId);

            this._updateProgressDisplay(uploadId, data);

            if (['completed', 'failed'].includes(data.status)) {
                this._clearProgressInterval(uploadId);
                data.status === 'completed' ? this._showCompletedState(uploadId, uploadData) : this._showErrorState(uploadId, data.message);
            }
        } catch (error) {
            console.error('Помилка перевірки прогресу:', error);
            this.removeUpload(uploadId);
        }
    }

    _updateProgressDisplay(uploadId, { progress = 0, stage = 'unknown', message = 'Обробка...' }) {
        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (!progressElement) return;

        const stageTexts = {
            queued: 'В черзі',
            downloading: 'Завантаження',
            analyzing: 'Аналіз відео',
            converting: 'Конвертація',
            finalizing: 'Завершення',
            completed: 'Завершено',
            failed: 'Помилка'
        };

        const elements = {
            statusText: progressElement.querySelector('.status-text'),
            progressPercentage: progressElement.querySelector('.progress-percentage'),
            progressFill: progressElement.querySelector('.progress-fill'),
            progressBar: progressElement.querySelector('.progress-bar'),
            progressStage: progressElement.querySelector('.progress-stage')
        };

        elements.statusText.textContent = stageTexts[stage] || stage;
        elements.progressPercentage.textContent = `${progress}%`;
        elements.progressFill.style.width = `${progress}%`;
        elements.progressFill.setAttribute('data-stage', stage);
        elements.progressStage.textContent = message;

        elements.progressBar.style.setProperty('--progress-width', `${progress}%`);
        elements.progressBar.setAttribute('data-stage', stage);
        elements.progressBar.setAttribute('data-progress', progress.toString());
    }

    _showCompletedState(uploadId, uploadData) {
        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (!progressElement) return;

        const azureFilePathParam = uploadData.azure_file_path ?
            encodeURIComponent(JSON.stringify(uploadData.azure_file_path)) : '';

        progressElement.querySelector('.upload-actions').innerHTML = `
            ${azureFilePathParam ?
                `<button class="btn btn-success" onclick="window.location.href='/annotator?azure_file_path=${azureFilePathParam}'">Перейти до анотування</button>` :
                `<button class="btn btn-success" onclick="window.location.href='/annotator'">Перейти до анотування</button>`
            }
            <button class="btn btn-secondary" onclick="videoUploader.removeUpload('${uploadId}')">Приховати</button>
        `;

        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();

        setTimeout(() => {
            if (document.getElementById(`progress-${uploadId}`)) {
                this.removeUpload(uploadId);
            }
        }, 30000);
    }

    _showErrorState(uploadId, errorMessage) {
        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (progressElement) {
            progressElement.querySelector('.progress-stage').innerHTML =
                `<span style="color: #e74c3c;">Помилка: ${utils.escapeHtml(errorMessage)}</span>`;
        }

        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();
    }

    removeUpload(uploadId) {
        this._clearProgressInterval(uploadId);
        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();

        document.getElementById(`progress-${uploadId}`)?.remove();

        if (this.elements.result.children.length === 0) {
            this.elements.result.classList.add('hidden');
        }
    }

    _clearProgressInterval(uploadId) {
        const interval = this.progressIntervals.get(uploadId);
        if (interval) {
            clearInterval(interval);
            this.progressIntervals.delete(uploadId);
        }
    }

    _saveUploadsToStorage() {
        localStorage.setItem('activeUploads', JSON.stringify(Array.from(this.activeUploads.values())));
    }

    async _loadSavedUploads() {
        try {
            const saved = localStorage.getItem('activeUploads');
            if (!saved) return;

            const uploadsArray = JSON.parse(saved);

            for (const uploadData of uploadsArray) {
                const hoursSinceUpload = (Date.now() - uploadData.timestamp) / (1000 * 60 * 60);

                if (hoursSinceUpload < 24 && await this._validateTaskExists(uploadData.taskId)) {
                    this.activeUploads.set(uploadData.id, uploadData);
                    this._showProgressBar(uploadData);
                    this._startProgressTracking(uploadData.id);
                }
            }

            if (this.activeUploads.size > 0) {
                this.elements.result.classList.remove('hidden');
            }

            this._saveUploadsToStorage();
        } catch (error) {
            console.error('Помилка завантаження збережених завантажень:', error);
            localStorage.removeItem('activeUploads');
        }
    }

    async _validateTaskExists(taskId) {
        try {
            return !!(await api.get(`/video/task/${taskId}/status`));
        } catch {
            return false;
        }
    }

    _resetForm() {
        Object.assign(this.elements.videoUrl, { value: '', style: { borderColor: '' } });
        this.elements.downloadAllFolder.checked = false;
        this._handleFolderCheckboxChange();
        this._setButtonLoading(false);
    }

    _setButtonLoading(loading) {
        Object.assign(this.elements.uploadBtn, {
            disabled: loading,
            textContent: loading ? 'Реєструємо...' : 'Зареєструвати відео'
        });
        this.elements.uploadBtn.classList.toggle('loading', loading);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.videoUploader = new VideoUploader();
});