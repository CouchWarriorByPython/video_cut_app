class VideoUploader {
    constructor() {
        this.elements = {
            videoUrl: document.getElementById('video-url'),
            metadataWhere: document.getElementById('metadata-where'),
            metadataWhen: document.getElementById('metadata-when'),
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
        this.elements.videoUrl.addEventListener('input', () => this._validateUrl());
    }

    async _handleUpload() {
        const formData = this._getFormData();

        if (!this._validateForm(formData)) {
            return;
        }

        UI.setButtonState(this.elements.uploadBtn, true, 'Реєструємо...');

        try {
            const data = await Auth.authenticatedRequest('/upload', {
                method: 'POST',
                body: JSON.stringify(formData)
            });

            if (!data) return;

            this._handleUploadResponse(data);
            this._resetForm();
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'upload');
            await showNotification(message, 'error');
        } finally {
            UI.setButtonState(this.elements.uploadBtn, false, 'Зареєструвати відео');
        }
    }

    _getFormData() {
        return {
            video_url: this.elements.videoUrl.value.trim(),
            where: this.elements.metadataWhere.value.trim() || null,
            when: this.elements.metadataWhen.value.trim() || null
        };
    }

    _validateForm(data) {
        UI.clearFormErrors(document.querySelector('form') || document);

        if (!data.video_url) {
            UI.setFieldValidation(this.elements.videoUrl, false, 'Поле є обовʼязковим');
            showNotification('Будь ласка, вкажіть Azure Blob URL відео', 'error');
            return false;
        }

        if (!Validators.isValidAzureUrl(data.video_url)) {
            UI.setFieldValidation(this.elements.videoUrl, false, 'Некоректний Azure URL');
            showNotification('Некоректний Azure Blob URL. Перевірте формат посилання', 'error');
            return false;
        }

        if (data.where && !Validators.isValidLocation(data.where)) {
            UI.setFieldValidation(this.elements.metadataWhere, false, 'Тільки англійські літери');
            showNotification('Локація може містити тільки англійські літери, пробіли, дефіси та підкреслення', 'error');
            return false;
        }

        if (data.when && !Validators.isValidDate(data.when)) {
            UI.setFieldValidation(this.elements.metadataWhen, false, `Формат: ${CONFIG.DATE_FORMAT}`);
            showNotification(`Дата повинна бути у форматі ${CONFIG.DATE_FORMAT} (8 цифр)`, 'error');
            return false;
        }

        return true;
    }

    _validateUrl() {
        const url = this.elements.videoUrl.value.trim();
        if (!url) {
            UI.setFieldValidation(this.elements.videoUrl, true);
            return;
        }

        const isValid = Validators.isValidAzureUrl(url);
        UI.setFieldValidation(this.elements.videoUrl, isValid,
            isValid ? '' : 'Некоректний Azure URL');
    }

    _handleUploadResponse(data) {
        if (data.success) {
            const uploadData = {
                id: Utils.generateId(),
                taskId: data.conversion_task_id,
                azure_link: data.azure_link,
                filename: data.filename,
                message: data.message,
                timestamp: Date.now()
            };

            this.activeUploads.set(uploadData.id, uploadData);
            this._saveUploadsToStorage();
            this._showProgressBar(uploadData);
            this._startProgressTracking(uploadData.id);
        } else {
            showNotification(data.message || 'Невідома помилка при реєстрації відео', 'error');
        }
    }

    _showProgressBar(uploadData) {
        const progressHTML = `
            <div id="progress-${uploadData.id}" class="upload-progress-item">
                <div class="upload-info">
                    <h3>Обробка відео</h3>
                    <p><strong>Файл:</strong> ${Utils.escapeHtml(uploadData.filename)}</p>
                    <p><strong>Azure посилання:</strong></p>
                    <p class="url-display">${Utils.escapeHtml(uploadData.azure_link)}</p>
                </div>
                <div class="progress-container">
                    <div class="progress-status">
                        <span class="status-text">Ініціалізація...</span>
                        <span class="progress-percentage">0%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                    <div class="progress-stage">Чекаємо початку обробки...</div>
                </div>
                <div class="upload-actions">
                    <button class="btn btn-secondary" onclick="videoUploader.removeUpload('${uploadData.id}')">Приховати</button>
                </div>
            </div>
        `;

        if (this.elements.result.children.length === 0) {
            this.elements.result.innerHTML = progressHTML;
        } else {
            this.elements.result.insertAdjacentHTML('afterbegin', progressHTML);
        }

        this.elements.result.classList.remove('hidden');
    }

    _startProgressTracking(uploadId) {
        const interval = setInterval(() => {
            this._checkTaskProgress(uploadId);
        }, 2000);

        this.progressIntervals.set(uploadId, interval);
    }

    async _checkTaskProgress(uploadId) {
        const uploadData = this.activeUploads.get(uploadId);
        if (!uploadData) {
            this._clearProgressInterval(uploadId);
            return;
        }

        try {
            const data = await Auth.authenticatedRequest(`/task_status/${uploadData.taskId}`);
            if (!data) {
                this.removeUpload(uploadId);
                return;
            }

            this._updateProgressDisplay(uploadId, data);

            if (data.status === 'completed' || data.status === 'failed') {
                this._clearProgressInterval(uploadId);

                if (data.status === 'completed') {
                    this._showCompletedState(uploadId, uploadData);
                } else {
                    this._showErrorState(uploadId, data.message);
                }
            }
        } catch (error) {
            console.error('Помилка перевірки прогресу:', error);
            this.removeUpload(uploadId);
        }
    }

    _updateProgressDisplay(uploadId, progressData) {
        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (!progressElement) return;

        const statusText = progressElement.querySelector('.status-text');
        const progressPercentage = progressElement.querySelector('.progress-percentage');
        const progressFill = progressElement.querySelector('.progress-fill');
        const progressStage = progressElement.querySelector('.progress-stage');

        const progress = progressData.progress || 0;
        const stage = progressData.stage || 'unknown';
        const message = progressData.message || 'Обробка...';

        const stageTexts = {
            'queued': 'В черзі',
            'downloading': 'Завантаження',
            'analyzing': 'Аналіз відео',
            'converting': 'Конвертація',
            'finalizing': 'Завершення',
            'completed': 'Завершено',
            'failed': 'Помилка'
        };

        statusText.textContent = stageTexts[stage] || stage;
        progressPercentage.textContent = `${progress}%`;
        progressFill.style.width = `${progress}%`;
        progressStage.textContent = message;

        progressFill.className = `progress-fill ${stage}`;
    }

    _showCompletedState(uploadId, uploadData) {
        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (!progressElement) return;

        const actionsDiv = progressElement.querySelector('.upload-actions');
        actionsDiv.innerHTML = `
            <button class="btn btn-success" onclick="window.location.href='${CONFIG.PAGES.ANNOTATOR}'">
                Перейти до анотування
            </button>
            <button class="btn btn-secondary" onclick="videoUploader.removeUpload('${uploadId}')">Приховати</button>
        `;

        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();
    }

    _showErrorState(uploadId, errorMessage) {
        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (!progressElement) return;

        const progressStage = progressElement.querySelector('.progress-stage');
        progressStage.innerHTML = `<span style="color: #e74c3c;">Помилка: ${Utils.escapeHtml(errorMessage)}</span>`;

        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();
    }

    removeUpload(uploadId) {
        this._clearProgressInterval(uploadId);
        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();

        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (progressElement) {
            progressElement.remove();
        }

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
        const uploadsArray = Array.from(this.activeUploads.values());
        localStorage.setItem('activeUploads', JSON.stringify(uploadsArray));
    }

    async _loadSavedUploads() {
        try {
            const saved = localStorage.getItem('activeUploads');
            if (!saved) return;

            const uploadsArray = JSON.parse(saved);

            for (const uploadData of uploadsArray) {
                const hoursSinceUpload = (Date.now() - uploadData.timestamp) / (1000 * 60 * 60);

                if (hoursSinceUpload < 24) {
                    const taskExists = await this._validateTaskExists(uploadData.taskId);
                    if (taskExists) {
                        this.activeUploads.set(uploadData.id, uploadData);
                        this._showProgressBar(uploadData);
                        this._startProgressTracking(uploadData.id);
                    }
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
            const response = await Auth.authenticatedRequest(`/task_status/${taskId}`);
            return !!response;
        } catch (error) {
            return false;
        }
    }

    _resetForm() {
        this.elements.videoUrl.value = '';
        this.elements.metadataWhere.value = '';
        this.elements.metadataWhen.value = '';
        UI.clearFormErrors(document);
        UI.setButtonState(this.elements.uploadBtn, false, 'Зареєструвати відео');
    }
}

/**
 * Ініціалізація при завантаженні сторінки
 */
document.addEventListener('DOMContentLoaded', () => {
    window.videoUploader = new VideoUploader();
});