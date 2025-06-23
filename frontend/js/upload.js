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
            const data = await api.post('/upload', formData);
            if (data) {
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
            if (!validators.azureUrl(url) && !data.download_all_folder) {
                errors.push(`URL #${index + 1} некоректний`);
            } else if (data.download_all_folder && !url.includes('.blob.core.windows.net')) {
                errors.push('URL папки має бути з Azure Blob Storage');
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
        if (data.success) {
            if (data.tasks && Array.isArray(data.tasks)) {
                // Багато відео
                data.tasks.forEach(task => {
                    const uploadData = {
                        id: utils.generateId(),
                        taskId: task.task_id,
                        azure_file_path: task.azure_file_path,
                        filename: task.filename,
                        message: task.message,
                        timestamp: Date.now()
                    };

                    this.activeUploads.set(uploadData.id, uploadData);
                    this._showProgressBar(uploadData);
                    this._startProgressTracking(uploadData.id);
                });
                this._saveUploadsToStorage();
            } else {
                // Одне відео
                const uploadData = {
                    id: utils.generateId(),
                    taskId: data.conversion_task_id,
                    azure_file_path: data.azure_file_path,
                    filename: data.filename,
                    message: data.message,
                    timestamp: Date.now()
                };

                this.activeUploads.set(uploadData.id, uploadData);
                this._saveUploadsToStorage();
                this._showProgressBar(uploadData);
                this._startProgressTracking(uploadData.id);
            }
        } else {
            notify(data.message || 'Невідома помилка при реєстрації відео', 'error');
        }
    }

    _showProgressBar(uploadData) {
        const azureUrl = utils.azureFilePathToUrl(uploadData.azure_file_path);
        const progressHTML = `
            <div id="progress-${uploadData.id}" class="upload-progress-item">
                <div class="upload-info">
                    <h3>Обробка відео</h3>
                    <p><strong>Файл:</strong> ${utils.escapeHtml(uploadData.filename)}</p>
                    <p><strong>Azure посилання:</strong></p>
                    <p class="url-display">${utils.escapeHtml(azureUrl)}</p>
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
        const interval = setInterval(() => this._checkTaskProgress(uploadId), 2000);
        this.progressIntervals.set(uploadId, interval);
    }

    async _checkTaskProgress(uploadId) {
        const uploadData = this.activeUploads.get(uploadId);
        if (!uploadData) return this._clearProgressInterval(uploadId);

        try {
            const data = await api.get(`/task_status/${uploadData.taskId}`);
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

        const azureFilePathParam = encodeURIComponent(JSON.stringify(uploadData.azure_file_path));

        progressElement.querySelector('.upload-actions').innerHTML = `
            <button class="btn btn-success" onclick="window.location.href='/annotator?azure_file_path=${azureFilePathParam}'">Перейти до анотування</button>
            <button class="btn btn-secondary" onclick="videoUploader.removeUpload('${uploadId}')">Приховати</button>
        `;

        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();

        // Автоматично приховуємо через 30 секунд
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
            return !!(await api.get(`/task_status/${taskId}`));
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