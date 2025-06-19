class VideoAnnotator {
    constructor() {
        this.elements = this._initElements();
        this.videosData = [];
        this.state = {
            currentAzureFilePath: null,
            videoFileName: null,
            projectFragments: { 'motion-det': [], 'tracking': [], 'mil-hardware': [], 're-id': [] },
            unfinishedFragments: { 'motion-det': null, 'tracking': null, 'mil-hardware': null, 're-id': null },
            activeProjects: []
        };
        this.statusCheckInterval = null;
        this.jsonModal = new BaseModal('json-modal');
        this.projectModal = new BaseModal('project-modal');
        this._init();
    }

    _initElements() {
        const $ = id => document.getElementById(id);
        const metaFields = ['skip-video', 'uav-type', 'video-content', 'is-urban', 'has-osd', 'is-analog', 'night-video', 'multiple-streams', 'has-infantry', 'has-explosions'];
        return {
            videoSelector: $('video-selector'), videoSelect: $('video-select'), loadVideoBtn: $('load-video-btn'),
            backToListBtn: $('back-to-list-btn'), videoEditor: $('video-editor'), videoPlayer: $('video-player'),
            timeline: $('timeline'), timelineProgress: $('timeline-progress'), startFragmentBtn: $('start-fragment'),
            endFragmentBtn: $('end-fragment'), cancelFragmentBtn: $('cancel-fragment'), fragmentsList: $('fragments-list'),
            saveFragmentsBtn: $('save-fragments'), projectCheckboxes: document.querySelectorAll('input[name="project"]'),
            videoFilenameSpan: document.querySelector('#video-filename span'), unfinishedFragmentsStatus: $('unfinished-fragments-status'),
            metadataForm: Object.fromEntries(metaFields.map((field, i) => [
                ['skipVideo', 'uavType', 'videoContent', 'isUrban', 'hasOsd', 'isAnalog', 'nightVideo', 'multipleStreams', 'hasInfantry', 'hasExplosions'][i],
                $(field)
            ]))
        };
    }

    _init() {
        this._setupEvents();
        this._loadVideoList();
        this._syncActiveProjects();
        this._checkUrlParams();
    }

    _setupEvents() {
        const events = [
            [this.elements.loadVideoBtn, 'click', () => this._handleLoadVideo()],
            [this.elements.backToListBtn, 'click', () => this.goBackToVideoList()],
            [this.elements.startFragmentBtn, 'click', () => this._handleStartFragment()],
            [this.elements.endFragmentBtn, 'click', () => this._handleFragmentAction('end')],
            [this.elements.cancelFragmentBtn, 'click', () => this._handleFragmentAction('cancel')],
            [this.elements.saveFragmentsBtn, 'click', () => this._handleSaveFragments()],
            [document.getElementById('view-json'), 'click', () => this._showJson()],
            [this.elements.videoPlayer, 'timeupdate', () => this._updateTimelineProgress()],
            [this.elements.videoPlayer, 'loadedmetadata', () => this._initVideoPlayer()],
            [this.elements.videoPlayer, 'error', () => this._handleVideoError()],
            [this.elements.timeline, 'click', e => this._handleTimelineClick(e)],
            [this.elements.metadataForm.skipVideo, 'change', () => this._handleSkipChange()]
        ];
        events.forEach(([el, event, handler]) => el?.addEventListener(event, handler));
        this.elements.projectCheckboxes.forEach(cb => cb.addEventListener('change', () => this._syncActiveProjects()));
    }

    _showJson() {
        document.getElementById('json-content').textContent = JSON.stringify(this._prepareJsonData(), null, 2);
        this.jsonModal.open();
    }

    _checkUrlParams() {
        const azureFilePathParam = new URLSearchParams(window.location.search).get('azure_file_path');
        if (azureFilePathParam) {
            try {
                const azureFilePath = JSON.parse(decodeURIComponent(azureFilePathParam));
                this._selectVideoByAzureFilePath(azureFilePath);
            } catch (e) {
                console.error('Error parsing azure_file_path parameter:', e);
            }
        }
    }

    async _loadVideoList() {
        try {
            const data = await api.get('/get_videos');
            if (data?.success && data.videos?.length) {
                this._populateVideoSelect(data.videos);
            } else {
                this.elements.videoSelect.innerHTML = '<option value="">Немає доступних відео</option>';
            }
        } catch (error) {
            console.error('Error loading videos:', error);
            this.elements.videoSelect.innerHTML = '<option value="">Помилка завантаження відео</option>';
        }
    }

    _populateVideoSelect(videos) {
        this.elements.videoSelect.innerHTML = '<option value="">Виберіть відео...</option>' +
            videos.map((video, index) => {
                const { indicator, ready } = this._getStatusData(video.status);
                const videoIndex = index; // Використовуємо індекс для ідентифікації
                return `<option value="${videoIndex}" data-video-id="${video.id}" data-filename="${video.filename || ''}"
                        data-video-index="${videoIndex}" data-status="${video.status}" ${!ready ? 'disabled' : ''}>
                        ${indicator} ${video.filename || video.azure_file_path.blob_path.split('/').pop() || `Відео #${video.id}`}</option>`;
            }).join('');

        // Зберігаємо відео дані для доступу за індексом
        this.videosData = videos;
    }

    _getStatusData(status) {
        const statusMap = {
            'queued': { indicator: '⏳', message: 'В черзі на обробку...', ready: false },
            'downloading': { indicator: '⬇️', message: 'Завантаження з Azure Storage...', ready: false },
            'analyzing': { indicator: '🔍', message: 'Аналіз характеристик відео...', ready: false },
            'converting': { indicator: '🔄', message: 'Конвертація відео для браузера...', ready: false },
            'ready': { indicator: '✅', message: '', ready: true },
            'not_annotated': { indicator: '✅', message: '', ready: true },
            'processing_failed': { indicator: '❌', message: 'Помилка обробки відео', ready: false },
            'download_failed': { indicator: '❌', message: 'Помилка завантаження з Azure Storage', ready: false },
            'conversion_failed': { indicator: '❌', message: 'Помилка конвертації відео', ready: false },
            'analysis_failed': { indicator: '❌', message: 'Помилка аналізу відео', ready: false },
            'annotated': { indicator: '✓', message: '', ready: true }
        };
        return statusMap[status] || { indicator: '❓', message: 'Обробка відео...', ready: false };
    }

    _selectVideoByAzureFilePath(azureFilePath) {
    // Шукаємо відео за azure_file_path у збережених даних
    const videoIndex = this.videosData?.findIndex(video =>
        utils.compareAzureFilePaths(video.azure_file_path, azureFilePath)
    );

    if (videoIndex !== undefined && videoIndex >= 0) {
        this.elements.videoSelect.value = videoIndex.toString();
        this._handleLoadVideo();
    } else {
        console.warn(`Відео з Azure File Path не знайдено`);
        this._loadVideoList();
        setTimeout(() => {
            const retryIndex = this.videosData?.findIndex(video =>
                utils.compareAzureFilePaths(video.azure_file_path, azureFilePath)
            );
            if (retryIndex !== undefined && retryIndex >= 0) {
                this.elements.videoSelect.value = retryIndex.toString();
                this._handleLoadVideo();
            }
        }, 1000);
    }
}

    async _handleLoadVideo() {
    const selectedIndex = this.elements.videoSelect.value;
    if (!selectedIndex || !this.videosData) return notify('Будь ласка, виберіть відео', 'warning');

    const video = this.videosData[parseInt(selectedIndex)];
    if (!video) return notify('Помилка обробки даних відео', 'error');

    const azureFilePath = video.azure_file_path;
    const filename = video.filename;
    const status = video.status;

    const { ready } = this._getStatusData(status);

    if (!ready) {
        this._showVideoProcessingStatus(azureFilePath, filename, status);
    } else {
        this._loadVideoForAnnotation(azureFilePath, filename);
    }
}

    _showVideoProcessingStatus(azureFilePath, filename, status) {
        this.elements.videoSelector.style.display = 'none';
        this.elements.videoEditor.innerHTML = `
            <div class="card">
                <h3>Відео обробляється</h3>
                <p><strong>Файл:</strong> ${utils.escapeHtml(filename)}</p>
                <p class="status-text">Статус: ${this._getStatusData(status).message}</p>
                <div class="loading-spinner"></div>
                <div style="margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="location.reload()">Оновити сторінку</button>
                    <button id="back-to-list-btn" class="btn">Вибрати інше відео</button>
                </div>
            </div>
        `;
        this.elements.videoEditor.classList.remove('hidden');
        document.getElementById('back-to-list-btn')?.addEventListener('click', () => this.goBackToVideoList());
        this.state.currentAzureFilePath = azureFilePath;
        this._startVideoStatusChecking(azureFilePath);
    }

    _startVideoStatusChecking(azureFilePath) {
        clearInterval(this.statusCheckInterval);
        this.statusCheckInterval = setInterval(() => this._checkVideoStatus(azureFilePath), 3000);
    }

    async _checkVideoStatus(azureFilePath) {
        try {
            const data = await api.post('/video_status', { azure_file_path: azureFilePath });
            if (!data) return clearInterval(this.statusCheckInterval);

            this._updateVideoStatusDisplay(data);

            if (data.ready_for_annotation) {
                clearInterval(this.statusCheckInterval);
                location.reload();
            } else if (data.status.includes('failed')) {
                clearInterval(this.statusCheckInterval);
                this._showProcessingError(data.status);
            }
        } catch (error) {
            console.error('Помилка перевірки статусу відео:', error);
        }
    }

    _updateVideoStatusDisplay(statusData) {
        const statusElement = document.querySelector('.status-text');
        if (statusElement) statusElement.textContent = `Статус: ${this._getStatusData(statusData.status).message}`;
    }

    _showProcessingError(status) {
        const errorMessages = {
            'download_failed': 'Не вдалося завантажити відео з Azure Storage. Перевірте посилання.',
            'conversion_failed': 'Не вдалося конвертувати відео в web-сумісний формат.',
            'analysis_failed': 'Не вдалося проаналізувати характеристики відео.'
        };

        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `
            <h3>Помилка обробки відео</h3>
            <p>${errorMessages[status] || 'Не вдалося обробити відео.'}</p>
            <p>Спробуйте завантажити відео ще раз або оберіть інший файл.</p>
        `;

        this.elements.videoEditor.querySelector('.card')?.replaceWith(errorDiv);
    }

    goBackToVideoList() {
        clearInterval(this.statusCheckInterval);
        this.elements.videoEditor.classList.add('hidden');
        this.elements.videoSelector.style.display = 'block';
        this._loadVideoList();
    }

    _loadVideoForAnnotation(azureFilePath, filename) {
        this.elements.videoSelector.style.display = 'none';
        this.elements.videoEditor.classList.remove('hidden');

        const videoUrl = `/get_video?azure_file_path=${encodeURIComponent(JSON.stringify(azureFilePath))}&token=${encodeURIComponent(auth.token)}`;
        this.elements.videoPlayer.src = videoUrl;
        this.elements.videoPlayer.load();

        this.elements.videoFilenameSpan.textContent = filename;
        Object.assign(this.state, { currentAzureFilePath: azureFilePath, videoFileName: filename });

        this._resetFragments();
        this._loadExistingAnnotations(azureFilePath);
        this._updateFragmentsList();
        this._clearAllMarkers();
        this._updateUnfinishedFragmentsUI();
        this._syncActiveProjects();
    }

    _resetFragments() {
        Object.assign(this.state, {
            projectFragments: { 'motion-det': [], 'tracking': [], 'mil-hardware': [], 're-id': [] },
            unfinishedFragments: { 'motion-det': null, 'tracking': null, 'mil-hardware': null, 're-id': null }
        });
    }

    async _loadExistingAnnotations(azureFilePath) {
        try {
            const data = await api.post('/get_annotation', { azure_file_path: azureFilePath });
            if (data?.success && data.annotation) {
                this._populateFormFromAnnotation(data.annotation);
                this._loadFragmentsFromAnnotation(data.annotation);
            }
        } catch (error) {
            console.error('Error loading annotations:', error);
        }
    }

    _populateFormFromAnnotation(annotation) {
        if (!annotation.metadata) return;

        const { metadata } = annotation;
        const form = this.elements.metadataForm;
        const mappings = [
            [form.skipVideo, 'checked', metadata.skip || false],
            [form.uavType, 'value', metadata.uav_type || ""],
            [form.videoContent, 'value', metadata.video_content || ""],
            [form.isUrban, 'checked', metadata.is_urban || false],
            [form.hasOsd, 'checked', metadata.has_osd || false],
            [form.isAnalog, 'checked', metadata.is_analog || false],
            [form.nightVideo, 'checked', metadata.night_video || false],
            [form.multipleStreams, 'checked', metadata.multiple_streams || false],
            [form.hasInfantry, 'checked', metadata.has_infantry || false],
            [form.hasExplosions, 'checked', metadata.has_explosions || false]
        ];
        mappings.forEach(([element, property, value]) => element[property] = value);
    }

    _loadFragmentsFromAnnotation(annotation) {
        if (!annotation.clips) return;

        Object.entries(annotation.clips).forEach(([projectType, clips]) => {
            if (Array.isArray(clips)) {
                this.state.projectFragments[projectType] = clips.map(clip => ({
                    id: clip.id,
                    start: utils.timeToSeconds(clip.start_time),
                    end: utils.timeToSeconds(clip.end_time),
                    start_formatted: clip.start_time,
                    end_formatted: clip.end_time,
                    project: projectType
                }));
            }
        });
        this._updateFragmentsList();
        this._visualizeFragments();
    }

    _handleVideoError() {
        const errorMessage = this.elements.videoPlayer.error?.message || 'Невідома помилка';
        console.error('Помилка відтворення відео:', errorMessage);

        const videoContainer = document.querySelector('.video-container');
        videoContainer.querySelector('.video-error')?.remove();

        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message video-error';
        errorDiv.innerHTML = `
            <h3>Помилка відтворення відео</h3>
            <p>Не вдалося завантажити відео: ${utils.escapeHtml(errorMessage)}</p>
            <p>Можливо, відео ще обробляється або має несумісний формат.</p>
            <div style="margin-top: 15px;">
                <button class="btn btn-secondary" onclick="videoAnnotator.retryVideoLoad()">Спробувати ще раз</button>
                <button class="btn" onclick="videoAnnotator.goBackToVideoList()">Вибрати інше відео</button>
            </div>
        `;
        videoContainer.appendChild(errorDiv);
    }

    retryVideoLoad() {
        document.querySelector('.video-error')?.remove();
        this.elements.videoPlayer.load();
    }

    _syncActiveProjects() {
        this.state.activeProjects = Array.from(this.elements.projectCheckboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);
        this._updateButtonStates();
    }

    _updateButtonStates() {
        const hasUnfinished = Object.values(this.state.unfinishedFragments).some(frag => frag !== null);
        this.elements.endFragmentBtn.disabled = !hasUnfinished;
        this.elements.cancelFragmentBtn.disabled = !hasUnfinished;
    }

    async _handleStartFragment() {
        if (!this.state.activeProjects.length) return notify('Необхідно вибрати хоча б один проєкт', 'warning');
        this._setFragmentStart();
    }

    _handleFragmentAction(action) {
        if (!this.state.activeProjects.length) return notify('Необхідно вибрати хоча б один проєкт', 'warning');

        const unfinishedProjects = this._getUnfinishedProjects();
        if (!unfinishedProjects.length) return notify('Немає незавершених фрагментів', 'warning');

        if (unfinishedProjects.length === 1) {
            action === 'end' ? this._setFragmentEnd(unfinishedProjects[0]) : this._cancelFragment(unfinishedProjects[0]);
        } else {
            this._showProjectModal(unfinishedProjects, project =>
                action === 'end' ? this._setFragmentEnd(project) : this._cancelFragment(project)
            );
        }
    }

    _getUnfinishedProjects() {
        return Object.keys(this.state.unfinishedFragments)
            .filter(project => this.state.unfinishedFragments[project] !== null && this.state.activeProjects.includes(project));
    }

    async _setFragmentStart() {
        const startTime = this.elements.videoPlayer.currentTime;

        for (const project of this.state.activeProjects) {
            if (this.state.unfinishedFragments[project]) {
                const confirmed = await confirm(`Для проєкту "${this._getProjectName(project)}" вже встановлена початкова мітка. Замінити її?`);
                if (!confirmed) continue;

                document.querySelector(`.fragment-marker.start[data-project="${project}"]`)?.remove();
            }

            const marker = document.createElement('div');
            Object.assign(marker, {
                className: `fragment-marker start ${project}`,
                title: `${this._getProjectName(project)}: ${utils.formatTime(startTime)}`
            });
            marker.dataset.project = project;
            marker.style.left = `${(startTime / this.elements.videoPlayer.duration) * 100}%`;
            this.elements.timeline.appendChild(marker);

            this.state.unfinishedFragments[project] = {
                start: startTime,
                start_formatted: utils.formatTime(startTime)
            };
        }
        this._updateUnfinishedFragmentsUI();
    }

    _showProjectModal(projects, callback) {
        const projectOptions = document.getElementById('project-options');
        projectOptions.innerHTML = projects.map(project =>
            `<div class="project-option ${project}">${this._getProjectName(project)} (початок: ${this.state.unfinishedFragments[project].start_formatted})</div>`
        ).join('');

        projectOptions.querySelectorAll('.project-option').forEach((option, i) => {
            option.addEventListener('click', () => {
                this.projectModal.close();
                callback(projects[i]);
            });
        });
        this.projectModal.open();
    }

    async _setFragmentEnd(project) {
        const endTime = this.elements.videoPlayer.currentTime;
        const unfinished = this.state.unfinishedFragments[project];
        if (!unfinished) return;

        const duration = endTime - unfinished.start;
        if (duration < 1) {
            const adjustedEndTime = unfinished.start + 1;
            if (adjustedEndTime > this.elements.videoPlayer.duration) {
                return notify('Неможливо створити кліп мінімальної тривалості 1 сек. Недостатньо відео.', 'error');
            }

            const confirmed = await confirm('Мінімальна тривалість кліпу - 1 секунда. Автоматично збільшити до 1 сек?');
            if (confirmed) {
                this.elements.videoPlayer.currentTime = adjustedEndTime;
                return this._setFragmentEnd(project);
            }
            return;
        }

        const completeFragment = {
            ...unfinished,
            end: endTime,
            end_formatted: utils.formatTime(endTime),
            id: Date.now() + Math.floor(Math.random() * 1000),
            project
        };

        this.state.projectFragments[project].push(completeFragment);
        this._createFragmentVisualization(completeFragment);
        this._removeStartMarker(project);
        this.state.unfinishedFragments[project] = null;
        this._updateUnfinishedFragmentsUI();
        this._updateFragmentsList();
    }

    _createFragmentVisualization(fragment) {
        const element = document.createElement('div');
        Object.assign(element, {
            className: `fragment ${fragment.project}`,
            title: `${fragment.start_formatted} - ${fragment.end_formatted} (${this._getProjectName(fragment.project)})`
        });
        Object.assign(element.dataset, { id: fragment.id, project: fragment.project });
        Object.assign(element.style, {
            left: `${(fragment.start / this.elements.videoPlayer.duration) * 100}%`,
            width: `${((fragment.end - fragment.start) / this.elements.videoPlayer.duration) * 100}%`
        });

        element.addEventListener('click', () => {
            this.elements.videoPlayer.currentTime = fragment.start;
            this.elements.videoPlayer.play();
        });
        this.elements.timeline.appendChild(element);
    }

    _removeStartMarker(project) {
        document.querySelector(`.fragment-marker.start[data-project="${project}"]`)?.remove();
    }

    _cancelFragment(project) {
        if (!this.state.unfinishedFragments[project]) return;
        this._removeStartMarker(project);
        this.state.unfinishedFragments[project] = null;
        this._updateUnfinishedFragmentsUI();
    }

    _updateUnfinishedFragmentsUI() {
        const unfinishedProjects = Object.keys(this.state.unfinishedFragments)
            .filter(project => this.state.unfinishedFragments[project] !== null);

        const hasUnfinished = unfinishedProjects.length > 0;
        this.elements.endFragmentBtn.disabled = !hasUnfinished || !this.state.activeProjects.length;
        this.elements.cancelFragmentBtn.disabled = !hasUnfinished || !this.state.activeProjects.length;

        if (hasUnfinished) {
            this.elements.unfinishedFragmentsStatus.innerHTML = '<h3>Незавершені фрагменти:</h3>' +
                unfinishedProjects.map(project =>
                    `<div class="badge ${project}">${this._getProjectName(project)}: ${this.state.unfinishedFragments[project].start_formatted}</div>`
                ).join('');
            this.elements.unfinishedFragmentsStatus.style.display = 'block';
        } else {
            this.elements.unfinishedFragmentsStatus.innerHTML = '';
            this.elements.unfinishedFragmentsStatus.style.display = 'none';
        }
    }

    _updateFragmentsList() {
        this.elements.fragmentsList.innerHTML = '';
        let totalFragments = 0;

        Object.entries(this.state.projectFragments).forEach(([project, fragments]) => {
            if (fragments.length > 0) {
                const header = document.createElement('h3');
                header.textContent = `${this._getProjectName(project)} (${fragments.length})`;
                this.elements.fragmentsList.appendChild(header);

                fragments.forEach((fragment, index) => {
                    const listItem = this._createFragmentListItem(fragment, index, project);
                    this.elements.fragmentsList.appendChild(listItem);
                    totalFragments++;
                });
            }
        });

        if (totalFragments === 0) {
            const emptyMessage = document.createElement('p');
            emptyMessage.textContent = 'Немає фрагментів';
            this.elements.fragmentsList.appendChild(emptyMessage);
        }
    }

    _createFragmentListItem(fragment, index, project) {
        const listItem = document.createElement('li');
        listItem.className = project;

        const timeInfo = document.createElement('span');
        timeInfo.textContent = `Фрагмент #${index + 1}: ${fragment.start_formatted} - ${fragment.end_formatted}`;

        const actions = document.createElement('div');
        const playBtn = document.createElement('button');
        Object.assign(playBtn, { textContent: '▶', className: 'btn' });
        playBtn.addEventListener('click', () => this._playFragment(fragment));

        const deleteBtn = document.createElement('button');
        Object.assign(deleteBtn, { textContent: 'Видалити', className: 'btn btn-danger' });
        deleteBtn.addEventListener('click', () => this._deleteFragment(fragment, project));

        actions.append(playBtn, deleteBtn);
        listItem.append(timeInfo, actions);
        return listItem;
    }

    _playFragment(fragment) {
        this.elements.videoPlayer.currentTime = fragment.start;
        this.elements.videoPlayer.play();

        const checkEnd = () => {
            if (this.elements.videoPlayer.currentTime >= fragment.end) {
                this.elements.videoPlayer.pause();
                this.elements.videoPlayer.removeEventListener('timeupdate', checkEnd);
            }
        };
        this.elements.videoPlayer.addEventListener('timeupdate', checkEnd);
    }

    _deleteFragment(fragment, project) {
        this.state.projectFragments[project] = this.state.projectFragments[project].filter(f => f.id !== fragment.id);
        document.querySelector(`.fragment[data-id="${fragment.id}"][data-project="${project}"]`)?.remove();
        this._updateFragmentsList();
    }

    _visualizeFragments() {
        this._clearAllMarkers();
        Object.values(this.state.projectFragments).flat().forEach(fragment => this._createFragmentVisualization(fragment));
    }

    _clearAllMarkers() {
        this.elements.timeline.querySelectorAll('.fragment, .fragment-marker').forEach(marker => marker.remove());
    }

    _initVideoPlayer() {
        this._updateUnfinishedFragmentsUI();
        this._updateButtonStates();
        this._visualizeFragments();
    }

    _updateTimelineProgress() {
        const progress = (this.elements.videoPlayer.currentTime / this.elements.videoPlayer.duration) * 100;
        this.elements.timelineProgress.style.width = `${progress}%`;
    }

    _handleTimelineClick(e) {
        const rect = this.elements.timeline.getBoundingClientRect();
        const position = (e.clientX - rect.left) / rect.width;
        this.elements.videoPlayer.currentTime = position * this.elements.videoPlayer.duration;
    }

    _handleSkipChange() {
        const metaFields = document.querySelectorAll('.meta-form .form-control, .meta-form input[type="checkbox"]:not(#skip-video)');
        metaFields.forEach(field => field.disabled = this.elements.metadataForm.skipVideo.checked);
    }

    _validateRequiredFields() {
        const form = this.elements.metadataForm;
        const errors = [];
        if (!form.uavType.value.trim()) errors.push('UAV (тип дрона)');
        if (!form.videoContent.value.trim()) errors.push('Контент відео');
        return errors;
    }

    _prepareJsonData() {
        const form = this.elements.metadataForm;
        const metadata = {
            skip: form.skipVideo.checked,
            uav_type: form.uavType.value,
            video_content: form.videoContent.value,
            is_urban: form.isUrban.checked,
            has_osd: form.hasOsd.checked,
            is_analog: form.isAnalog.checked,
            night_video: form.nightVideo.checked,
            multiple_streams: form.multipleStreams.checked,
            has_infantry: form.hasInfantry.checked,
            has_explosions: form.hasExplosions.checked
        };

        const formattedProjects = {};
        Object.entries(this.state.projectFragments).forEach(([project, fragments]) => {
            if (fragments.length > 0) {
                formattedProjects[project] = fragments.map((fragment, index) => ({
                    id: index,
                    start_time: fragment.start_formatted,
                    end_time: fragment.end_formatted
                }));
            }
        });

        return {
            azure_file_path: this.state.currentAzureFilePath,
            metadata,
            clips: formattedProjects
        };
    }

    async _handleSaveFragments() {
        const confirmed = await confirm('Ви впевнені, що хочете завершити анотацію? Після завершення відео буде відправлено на обробку і ви повернетесь до вибору відео.');
        if (!confirmed) return;

        await this._saveFragments();
    }

    async _saveFragments() {
        if (!this.elements.metadataForm.skipVideo.checked) {
            const validationErrors = this._validateRequiredFields();
            if (validationErrors.length > 0) {
                return notify(`Необхідно заповнити обов'язкові поля:\n• ${validationErrors.join('\n• ')}`, 'error');
            }
        }

        const totalFragments = Object.values(this.state.projectFragments).reduce((sum, fragments) => sum + fragments.length, 0);
        if (totalFragments === 0 && !this.elements.metadataForm.skipVideo.checked) {
            return notify('Немає фрагментів для збереження і відео не помічено як Skip', 'warning');
        }

        const unfinishedProjects = Object.keys(this.state.unfinishedFragments)
            .filter(project => this.state.unfinishedFragments[project] !== null);

        if (unfinishedProjects.length > 0) {
            const confirmed = await confirm('У вас є незавершені фрагменти, які не будуть збережені. Продовжити?');
            if (!confirmed) return;
        }

        try {
            const data = await api.post('/save_fragments', {
                azure_file_path: this.state.currentAzureFilePath,
                data: this._prepareJsonData()
            });

            if (data?.success) {
                await notify(data.message || 'Анотацію успішно завершено. Відео відправлено на обробку.', 'success');
                if (data.task_id) console.log('Task ID:', data.task_id);

                this.goBackToVideoList();
            } else {
                await notify('Помилка: ' + data?.error, 'error');
            }
        } catch (error) {
            await notify(error.message, 'error');
        }
    }

    _getProjectName(projectKey) {
        const names = {
            'motion-det': 'Motion Detection',
            'tracking': 'Tracking & Re-identification',
            'mil-hardware': 'Mil Hardware Detection',
            're-id': 'Re-ID'
        };
        return names[projectKey] || projectKey;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.videoAnnotator = new VideoAnnotator();
});