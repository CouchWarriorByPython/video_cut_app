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
        this.elements.videoUrl.addEventListener('input', utils.debounce(() => this._validateUrl(), 300));
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
        return {
            video_url: this.elements.videoUrl.value.trim(),
            where: this.elements.metadataWhere.value.trim() || null,
            when: this.elements.metadataWhen.value.trim() || null
        };
    }

    _validateForm(data) {
        const errors = [
            !data.video_url && 'Azure Blob URL є обов\'язковим',
            data.video_url && !validators.azureUrl(data.video_url) && 'Некоректний Azure URL',
            data.where && !/^[A-Za-z\s\-_]+$/.test(data.where) && 'Локація може містити тільки англійські літери',
            data.when && !/^\d{8}$/.test(data.when) && 'Дата повинна бути у форматі РРРРММДД'
        ].filter(Boolean);

        if (errors.length > 0) {
            notify(errors.join('\n'), 'error');
            return false;
        }
        return true;
    }

    _validateUrl() {
        const url = this.elements.videoUrl.value.trim();
        if (url) {
            this.elements.videoUrl.style.borderColor = validators.azureUrl(url) ? '' : '#e74c3c';
        }
    }

    _handleUploadResponse(data) {
        if (data.success) {
            const uploadData = {
                id: utils.generateId(),
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
            notify(data.message || 'Невідома помилка при реєстрації відео', 'error');
        }
    }

    _showProgressBar(uploadData) {
        const progressHTML = `
            <div id="progress-${uploadData.id}" class="upload-progress-item">
                <div class="upload-info">
                    <h3>Обробка відео</h3>
                    <p><strong>Файл:</strong> ${utils.escapeHtml(uploadData.filename)}</p>
                    <p><strong>Azure посилання:</strong></p>
                    <p class="url-display">${utils.escapeHtml(uploadData.azure_link)}</p>
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
                data.status === 'completed' ? this._showCompletedState(uploadId) : this._showErrorState(uploadId, data.message);
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

        // Оновлюємо clip-path для shimmer ефекту
        elements.progressBar.style.setProperty('--progress-width', `${progress}%`);
        elements.progressBar.setAttribute('data-stage', stage);
        elements.progressBar.setAttribute('data-progress', progress.toString());
    }

    _showCompletedState(uploadId) {
        const progressElement = document.getElementById(`progress-${uploadId}`);
        if (!progressElement) return;

        progressElement.querySelector('.upload-actions').innerHTML = `
            <button class="btn btn-success" onclick="window.location.href='/annotator'">Перейти до анотування</button>
            <button class="btn btn-secondary" onclick="videoUploader.removeUpload('${uploadId}')">Приховати</button>
        `;

        this.activeUploads.delete(uploadId);
        this._saveUploadsToStorage();
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
        Object.assign(this.elements.metadataWhere, { value: '' });
        Object.assign(this.elements.metadataWhen, { value: '' });
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