/**
 * Модуль анотування відео
 */

class VideoAnnotator {
    constructor() {
        this.elements = this._initializeElements();
        this.state = this._initializeState();
        this.statusCheckInterval = null;

        this._init();
    }

    _initializeElements() {
        return {
            videoSelector: document.getElementById('video-selector'),
            videoSelect: document.getElementById('video-select'),
            loadVideoBtn: document.getElementById('load-video-btn'),
            videoEditor: document.getElementById('video-editor'),
            videoPlayer: document.getElementById('video-player'),
            timeline: document.getElementById('timeline'),
            timelineProgress: document.getElementById('timeline-progress'),
            startFragmentBtn: document.getElementById('start-fragment'),
            endFragmentBtn: document.getElementById('end-fragment'),
            cancelFragmentBtn: document.getElementById('cancel-fragment'),
            fragmentsList: document.getElementById('fragments-list'),
            saveFragmentsBtn: document.getElementById('save-fragments'),
            projectCheckboxes: document.querySelectorAll('input[name="project"]'),
            videoFilenameSpan: document.querySelector('#video-filename span'),
            unfinishedFragmentsStatus: document.getElementById('unfinished-fragments-status'),
            metadataForm: {
                skipVideo: document.getElementById('skip-video'),
                uavType: document.getElementById('uav-type'),
                videoContent: document.getElementById('video-content'),
                isUrban: document.getElementById('is-urban'),
                hasOsd: document.getElementById('has-osd'),
                isAnalog: document.getElementById('is-analog'),
                nightVideo: document.getElementById('night-video'),
                multipleStreams: document.getElementById('multiple-streams'),
                hasInfantry: document.getElementById('has-infantry'),
                hasExplosions: document.getElementById('has-explosions')
            },
            modals: {
                viewJson: document.getElementById('view-json'),
                jsonModal: document.getElementById('json-modal'),
                jsonContent: document.getElementById('json-content'),
                projectModal: document.getElementById('project-modal'),
                projectOptions: document.getElementById('project-options'),
                modalCloses: document.querySelectorAll('.modal-close')
            }
        };
    }

    _initializeState() {
        return {
            currentAzureLink: null,
            videoFileName: null,
            projectFragments: {
                'motion-det': [],
                'tracking': [],
                'mil-hardware': [],
                're-id': []
            },
            unfinishedFragments: {
                'motion-det': null,
                'tracking': null,
                'mil-hardware': null,
                're-id': null
            },
            activeProjects: []
        };
    }

    _init() {
        this._setupEventListeners();
        this._loadVideoList();
        this._syncActiveProjects();
        this._checkUrlParams();
    }

    _setupEventListeners() {
        this.elements.loadVideoBtn.addEventListener('click', () => this._handleLoadVideo());
        this.elements.startFragmentBtn.addEventListener('click', () => this._handleStartFragment());
        this.elements.endFragmentBtn.addEventListener('click', () => this._handleEndFragment());
        this.elements.cancelFragmentBtn.addEventListener('click', () => this._handleCancelFragment());
        this.elements.saveFragmentsBtn.addEventListener('click', () => this._saveFragments());
        this.elements.modals.viewJson.addEventListener('click', () => this._showJsonModal());

        this.elements.videoPlayer.addEventListener('timeupdate', () => this._updateTimelineProgress());
        this.elements.videoPlayer.addEventListener('loadedmetadata', () => this._initVideoPlayer());
        this.elements.videoPlayer.addEventListener('error', () => this._handleVideoError());

        this.elements.timeline.addEventListener('click', (e) => this._handleTimelineClick(e));

        this.elements.projectCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => this._syncActiveProjects());
        });

        this.elements.metadataForm.skipVideo.addEventListener('change', () => this._handleSkipChange());

        this.elements.modals.modalCloses.forEach(closeBtn => {
            closeBtn.addEventListener('click', () => this._closeModals());
        });

        window.addEventListener('click', (e) => this._handleWindowClick(e));
    }

    _checkUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const azureLink = urlParams.get('azure_link');
        if (azureLink) {
            this._selectVideoByAzureLink(azureLink);
        }
    }

    async _loadVideoList() {
        try {
            const data = await Auth.authenticatedRequest('/get_videos');
            if (!data) return;

            if (data.success && data.videos && data.videos.length > 0) {
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
        this.elements.videoSelect.innerHTML = '<option value="">Виберіть відео...</option>';

        videos.forEach(video => {
            const option = document.createElement('option');
            option.value = video.azure_link;

            const statusIndicator = this._getStatusIndicator(video.status);
            option.textContent = `${statusIndicator} ${video.filename || video.azure_link.split('/').pop() || `Відео #${video.id}`}`;

            option.dataset.videoId = video.id;
            option.dataset.filename = video.filename || '';
            option.dataset.azureLink = video.azure_link;
            option.dataset.status = video.status;

            if (!this._isVideoReadyForAnnotation(video.status)) {
                option.disabled = true;
            }

            this.elements.videoSelect.appendChild(option);
        });
    }

    _getStatusIndicator(status) {
        const indicators = {
            'queued': '⏳',
            'downloading': '⬇️',
            'analyzing': '🔍',
            'converting': '🔄',
            'ready': '✅',
            'not_annotated': '✅',
            'processing_failed': '❌',
            'download_failed': '❌',
            'conversion_failed': '❌',
            'analysis_failed': '❌',
            'annotated': '✓'
        };
        return indicators[status] || '❓';
    }

    _isVideoReadyForAnnotation(status) {
        return ['ready', 'not_annotated'].includes(status);
    }

    _selectVideoByAzureLink(azureLink) {
        const option = this.elements.videoSelect.querySelector(`option[data-azure-link="${azureLink}"]`);
        if (option) {
            this.elements.videoSelect.value = option.value;
            this._handleLoadVideo();
        } else {
            console.warn(`Відео з Azure Link ${azureLink} не знайдено в списку`);
            this._loadVideoList();
            setTimeout(() => {
                const retryOption = this.elements.videoSelect.querySelector(`option[data-azure-link="${azureLink}"]`);
                if (retryOption) {
                    this.elements.videoSelect.value = retryOption.value;
                    this._handleLoadVideo();
                }
            }, 1000);
        }
    }

    async _handleLoadVideo() {
        const selectedVideo = this.elements.videoSelect.value;
        if (!selectedVideo) {
            await showNotification('Будь ласка, виберіть відео', 'warning');
            return;
        }

        const selectedOption = this.elements.videoSelect.options[this.elements.videoSelect.selectedIndex];
        const azureLink = selectedOption.dataset.azureLink;
        const filename = selectedOption.dataset.filename || selectedOption.textContent;
        const status = selectedOption.dataset.status;

        if (!this._isVideoReadyForAnnotation(status)) {
            this._showVideoProcessingStatus(azureLink, filename, status);
            return;
        }

        this._loadVideoForAnnotation(azureLink, filename);
    }

    _showVideoProcessingStatus(azureLink, filename, status) {
        this.elements.videoSelector.style.display = 'none';
        this.elements.videoEditor.innerHTML = `
            <div class="card">
                <h3>Відео обробляється</h3>
                <p><strong>Файл:</strong> ${Utils.escapeHtml(filename)}</p>
                <p class="status-text">Статус: ${this._getStatusMessage(status)}</p>
                <div class="loading-spinner"></div>
                <div style="margin-top: 20px;">
                    <button class="btn btn-secondary" onclick="location.reload()">Оновити сторінку</button>
                    <button class="btn" onclick="videoAnnotator.goBackToVideoList()">Вибрати інше відео</button>
                </div>
            </div>
        `;
        this.elements.videoEditor.classList.remove('hidden');

        this.state.currentAzureLink = azureLink;
        this._startVideoStatusChecking(azureLink);
    }

    _getStatusMessage(status) {
        const messages = {
            'queued': 'В черзі на обробку...',
            'downloading': 'Завантаження з Azure Storage...',
            'analyzing': 'Аналіз характеристик відео...',
            'converting': 'Конвертація відео для браузера...',
            'processing_failed': 'Помилка обробки відео',
            'download_failed': 'Помилка завантаження з Azure Storage',
            'conversion_failed': 'Помилка конвертації відео',
            'analysis_failed': 'Помилка аналізу відео'
        };
        return messages[status] || 'Обробка відео...';
    }

    _startVideoStatusChecking(azureLink) {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }

        this.statusCheckInterval = setInterval(() => {
            this._checkVideoStatus(azureLink);
        }, 3000);
    }

    async _checkVideoStatus(azureLink) {
        try {
            const data = await Auth.authenticatedRequest(`/video_status?azure_link=${encodeURIComponent(azureLink)}`);
            if (!data) {
                clearInterval(this.statusCheckInterval);
                return;
            }

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
        if (statusElement) {
            statusElement.textContent = `Статус: ${this._getStatusMessage(statusData.status)}`;
        }
    }

    _showProcessingError(status) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';

        let errorText = 'Не вдалося обробити відео.';
        if (status === 'download_failed') {
            errorText = 'Не вдалося завантажити відео з Azure Storage. Перевірте посилання.';
        } else if (status === 'conversion_failed') {
            errorText = 'Не вдалося конвертувати відео в web-сумісний формат.';
        } else if (status === 'analysis_failed') {
            errorText = 'Не вдалося проаналізувати характеристики відео.';
        }

        errorDiv.innerHTML = `
            <h3>Помилка обробки відео</h3>
            <p>${errorText}</p>
            <p>Спробуйте завантажити відео ще раз або оберіть інший файл.</p>
        `;

        const existingCard = this.elements.videoEditor.querySelector('.card');
        if (existingCard) {
            existingCard.replaceWith(errorDiv);
        }
    }

    goBackToVideoList() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }

        this.elements.videoEditor.classList.add('hidden');
        this.elements.videoSelector.style.display = 'block';
        this._loadVideoList();
    }

    _loadVideoForAnnotation(azureLink, filename) {
        this.elements.videoSelector.style.display = 'none';
        this.elements.videoEditor.classList.remove('hidden');

        const token = Auth.getAccessToken();
        const videoUrl = `/get_video?azure_link=${encodeURIComponent(azureLink)}&token=${encodeURIComponent(token)}`;
        this.elements.videoPlayer.src = videoUrl;
        this.elements.videoPlayer.load();

        this.elements.videoFilenameSpan.textContent = filename;
        this.state.currentAzureLink = azureLink;
        this.state.videoFileName = filename;

        this._resetFragments();
        this._loadExistingAnnotations(azureLink);
        this._updateFragmentsList();
        this._clearAllMarkers();
        this._updateUnfinishedFragmentsUI();
        this._syncActiveProjects();
    }

    _resetFragments() {
        this.state.projectFragments = {
            'motion-det': [],
            'tracking': [],
            'mil-hardware': [],
            're-id': []
        };

        this.state.unfinishedFragments = {
            'motion-det': null,
            'tracking': null,
            'mil-hardware': null,
            're-id': null
        };
    }

    async _loadExistingAnnotations(azureLink) {
        try {
            const data = await Auth.authenticatedRequest(`/get_annotation?azure_link=${encodeURIComponent(azureLink)}`);
            if (!data) return;

            if (data.success && data.annotation) {
                this._populateFormFromAnnotation(data.annotation);
                this._loadFragmentsFromAnnotation(data.annotation);
            }
        } catch (error) {
            console.error('Error loading annotations:', error);
        }
    }

    _populateFormFromAnnotation(annotation) {
        if (annotation.metadata) {
            const metadata = annotation.metadata;
            const form = this.elements.metadataForm;

            form.skipVideo.checked = metadata.skip || false;
            form.uavType.value = metadata.uav_type || "";
            form.videoContent.value = metadata.video_content || "";
            form.isUrban.checked = metadata.is_urban || false;
            form.hasOsd.checked = metadata.has_osd || false;
            form.isAnalog.checked = metadata.is_analog || false;
            form.nightVideo.checked = metadata.night_video || false;
            form.multipleStreams.checked = metadata.multiple_streams || false;
            form.hasInfantry.checked = metadata.has_infantry || false;
            form.hasExplosions.checked = metadata.has_explosions || false;
        }
    }

    _loadFragmentsFromAnnotation(annotation) {
        if (annotation.clips) {
            for (const projectType in annotation.clips) {
                if (Array.isArray(annotation.clips[projectType])) {
                    this.state.projectFragments[projectType] = annotation.clips[projectType].map(clip => {
                        const startSeconds = Utils.timeToSeconds(clip.start_time);
                        const endSeconds = Utils.timeToSeconds(clip.end_time);

                        return {
                            id: clip.id,
                            start: startSeconds,
                            end: endSeconds,
                            start_formatted: clip.start_time,
                            end_formatted: clip.end_time,
                            project: projectType
                        };
                    });
                }
            }
            this._updateFragmentsList();
            this._visualizeFragments();
        }
    }

    _handleVideoError() {
        const errorMessage = this.elements.videoPlayer.error ? this.elements.videoPlayer.error.message : 'Невідома помилка';
        console.error('Помилка відтворення відео:', errorMessage);

        const videoContainer = document.querySelector('.video-container');
        const existingError = videoContainer.querySelector('.video-error');
        if (existingError) {
            existingError.remove();
        }

        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message video-error';
        errorDiv.innerHTML = `
            <h3>Помилка відтворення відео</h3>
            <p>Не вдалося завантажити відео: ${Utils.escapeHtml(errorMessage)}</p>
            <p>Можливо, відео ще обробляється або має несумісний формат.</p>
            <div style="margin-top: 15px;">
                <button class="btn btn-secondary" onclick="videoAnnotator.retryVideoLoad()">Спробувати ще раз</button>
                <button class="btn" onclick="videoAnnotator.goBackToVideoList()">Вибрати інше відео</button>
            </div>
        `;

        videoContainer.appendChild(errorDiv);
    }

    retryVideoLoad() {
        const errorDiv = document.querySelector('.video-error');
        if (errorDiv) {
            errorDiv.remove();
        }
        this.elements.videoPlayer.load();
    }

    _syncActiveProjects() {
        this.state.activeProjects = [];
        this.elements.projectCheckboxes.forEach(checkbox => {
            if (checkbox.checked) {
                this.state.activeProjects.push(checkbox.value);
            }
        });
        this._updateButtonStates();
    }

    _updateButtonStates() {
        const hasUnfinishedFragments = Object.values(this.state.unfinishedFragments).some(frag => frag !== null);
        this.elements.endFragmentBtn.disabled = !hasUnfinishedFragments;
        this.elements.cancelFragmentBtn.disabled = !hasUnfinishedFragments;
    }

    async _handleStartFragment() {
        if (this.state.activeProjects.length === 0) {
            await showNotification('Необхідно вибрати хоча б один проєкт', 'warning');
            return;
        }
        this._setFragmentStart();
    }

    async _handleEndFragment() {
        if (this.state.activeProjects.length === 0) {
            await showNotification('Необхідно вибрати хоча б один проєкт', 'warning');
            return;
        }
        this._showEndFragmentModal();
    }

    async _handleCancelFragment() {
        if (this.state.activeProjects.length === 0) {
            await showNotification('Необхідно вибрати хоча б один проєкт', 'warning');
            return;
        }
        this._showCancelFragmentModal();
    }

    async _setFragmentStart() {
        const startTime = this.elements.videoPlayer.currentTime;

        for (const project of this.state.activeProjects) {
            if (this.state.unfinishedFragments[project]) {
                const confirmed = await showConfirm(`Для проєкту "${this._getProjectName(project)}" вже встановлена початкова мітка. Замінити її?`);
                if (!confirmed) {
                    continue;
                }

                const oldMarker = document.querySelector(`.fragment-marker.start[data-project="${project}"]`);
                if (oldMarker) {
                    this.elements.timeline.removeChild(oldMarker);
                }
            }

            const marker = document.createElement('div');
            marker.className = `fragment-marker start ${project}`;
            marker.dataset.project = project;
            marker.style.left = `${(startTime / this.elements.videoPlayer.duration) * 100}%`;
            marker.title = `${this._getProjectName(project)}: ${Utils.formatTime(startTime)}`;
            this.elements.timeline.appendChild(marker);

            this.state.unfinishedFragments[project] = {
                start: startTime,
                start_formatted: Utils.formatTime(startTime)
            };
        }

        this._updateUnfinishedFragmentsUI();
    }

    _showEndFragmentModal() {
        const unfinishedProjects = Object.keys(this.state.unfinishedFragments).filter(project =>
            this.state.unfinishedFragments[project] !== null && this.state.activeProjects.includes(project)
        );

        if (unfinishedProjects.length === 0) {
            showNotification('Немає незавершених фрагментів', 'warning');
            return;
        }

        if (unfinishedProjects.length === 1) {
            this._setFragmentEnd(unfinishedProjects[0]);
            return;
        }

        this._showProjectModal(unfinishedProjects, (project) => this._setFragmentEnd(project));
    }

    _showCancelFragmentModal() {
        const unfinishedProjects = Object.keys(this.state.unfinishedFragments).filter(project =>
            this.state.unfinishedFragments[project] !== null && this.state.activeProjects.includes(project)
        );

        if (unfinishedProjects.length === 0) {
            showNotification('Немає незавершених фрагментів', 'warning');
            return;
        }

        if (unfinishedProjects.length === 1) {
            this._cancelFragment(unfinishedProjects[0]);
            return;
        }

        this._showProjectModal(unfinishedProjects, (project) => this._cancelFragment(project));
    }

    _showProjectModal(projects, callback) {
        this.elements.modals.projectOptions.innerHTML = '';
        projects.forEach(project => {
            const option = document.createElement('div');
            option.className = `project-option ${project}`;
            option.textContent = `${this._getProjectName(project)} (початок: ${this.state.unfinishedFragments[project].start_formatted})`;
            option.addEventListener('click', () => {
                this.elements.modals.projectModal.style.display = 'none';
                callback(project);
            });
            this.elements.modals.projectOptions.appendChild(option);
        });

        this.elements.modals.projectModal.style.display = 'block';
    }

    async _setFragmentEnd(project) {
        const endTime = this.elements.videoPlayer.currentTime;

        if (!this.state.unfinishedFragments[project]) {
            return;
        }

        const duration = endTime - this.state.unfinishedFragments[project].start;
        if (duration < CONFIG.MIN_CLIP_DURATION) {
            const adjustedEndTime = this.state.unfinishedFragments[project].start + CONFIG.MIN_CLIP_DURATION;
            if (adjustedEndTime > this.elements.videoPlayer.duration) {
                await showNotification(`Неможливо створити кліп мінімальної тривалості ${CONFIG.MIN_CLIP_DURATION} сек. Недостатньо відео.`, 'error');
                return;
            }

            const confirmed = await showConfirm(`Мінімальна тривалість кліпу - ${CONFIG.MIN_CLIP_DURATION} секунда. Автоматично збільшити до ${CONFIG.MIN_CLIP_DURATION} сек?`);
            if (confirmed) {
                this.elements.videoPlayer.currentTime = adjustedEndTime;
                this._setFragmentEnd(project);
                return;
            } else {
                return;
            }
        }

        const completeFragment = {
            ...this.state.unfinishedFragments[project],
            end: endTime,
            end_formatted: Utils.formatTime(endTime),
            id: Date.now() + Math.floor(Math.random() * 1000),
            project: project
        };

        this.state.projectFragments[project].push(completeFragment);

        this._createFragmentVisualization(completeFragment);
        this._removeStartMarker(project);

        this.state.unfinishedFragments[project] = null;
        this._updateUnfinishedFragmentsUI();
        this._updateFragmentsList();
    }

    _createFragmentVisualization(fragment) {
        const fragmentElement = document.createElement('div');
        fragmentElement.className = `fragment ${fragment.project}`;
        fragmentElement.dataset.id = fragment.id;
        fragmentElement.dataset.project = fragment.project;
        fragmentElement.style.left = `${(fragment.start / this.elements.videoPlayer.duration) * 100}%`;
        fragmentElement.style.width = `${((fragment.end - fragment.start) / this.elements.videoPlayer.duration) * 100}%`;
        fragmentElement.title = `${fragment.start_formatted} - ${fragment.end_formatted} (${this._getProjectName(fragment.project)})`;

        fragmentElement.addEventListener('click', () => {
            this.elements.videoPlayer.currentTime = fragment.start;
            this.elements.videoPlayer.play();
        });

        this.elements.timeline.appendChild(fragmentElement);
    }

    _removeStartMarker(project) {
        const startMarker = document.querySelector(`.fragment-marker.start[data-project="${project}"]`);
        if (startMarker) {
            this.elements.timeline.removeChild(startMarker);
        }
    }

    _cancelFragment(project) {
        if (!this.state.unfinishedFragments[project]) {
            return;
        }

        this._removeStartMarker(project);
        this.state.unfinishedFragments[project] = null;
        this._updateUnfinishedFragmentsUI();
    }

    _updateUnfinishedFragmentsUI() {
        const unfinishedProjects = Object.keys(this.state.unfinishedFragments).filter(project =>
            this.state.unfinishedFragments[project] !== null
        );

        const hasUnfinished = unfinishedProjects.length > 0;
        this.elements.endFragmentBtn.disabled = !hasUnfinished || this.state.activeProjects.length === 0;
        this.elements.cancelFragmentBtn.disabled = !hasUnfinished || this.state.activeProjects.length === 0;

        if (hasUnfinished) {
            let statusHTML = '<h3>Незавершені фрагменти:</h3>';
            unfinishedProjects.forEach(project => {
                statusHTML += `<div class="badge ${project}">${this._getProjectName(project)}: ${this.state.unfinishedFragments[project].start_formatted}</div>`;
            });
            this.elements.unfinishedFragmentsStatus.innerHTML = statusHTML;
            this.elements.unfinishedFragmentsStatus.style.display = 'block';
        } else {
            this.elements.unfinishedFragmentsStatus.innerHTML = '';
            this.elements.unfinishedFragmentsStatus.style.display = 'none';
        }
    }

    _updateFragmentsList() {
        this.elements.fragmentsList.innerHTML = '';

        let totalFragments = 0;
        for (const project in this.state.projectFragments) {
            if (this.state.projectFragments[project].length > 0) {
                const projectHeader = document.createElement('h3');
                projectHeader.textContent = `${this._getProjectName(project)} (${this.state.projectFragments[project].length})`;
                this.elements.fragmentsList.appendChild(projectHeader);

                this.state.projectFragments[project].forEach((fragment, index) => {
                    const listItem = this._createFragmentListItem(fragment, index, project);
                    this.elements.fragmentsList.appendChild(listItem);
                    totalFragments++;
                });
            }
        }

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
        playBtn.textContent = '▶';
        playBtn.className = 'btn';
        playBtn.addEventListener('click', () => this._playFragment(fragment));

        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Видалити';
        deleteBtn.className = 'btn btn-danger';
        deleteBtn.addEventListener('click', () => this._deleteFragment(fragment, project));

        actions.appendChild(playBtn);
        actions.appendChild(deleteBtn);

        listItem.appendChild(timeInfo);
        listItem.appendChild(actions);

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

        const fragmentElement = document.querySelector(`.fragment[data-id="${fragment.id}"][data-project="${project}"]`);
        if (fragmentElement) {
            this.elements.timeline.removeChild(fragmentElement);
        }

        this._updateFragmentsList();
    }

    _visualizeFragments() {
        this._clearAllMarkers();

        for (const projectType in this.state.projectFragments) {
            this.state.projectFragments[projectType].forEach(fragment => {
                this._createFragmentVisualization(fragment);
            });
        }
    }

    _clearAllMarkers() {
        const markers = this.elements.timeline.querySelectorAll('.fragment, .fragment-marker');
        markers.forEach(marker => marker.remove());
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
        const time = position * this.elements.videoPlayer.duration;
        this.elements.videoPlayer.currentTime = time;
    }

    _handleSkipChange() {
        const metaFields = document.querySelectorAll('.meta-form .form-control, .meta-form input[type="checkbox"]:not(#skip-video)');
        metaFields.forEach(field => {
            field.disabled = this.elements.metadataForm.skipVideo.checked;
        });
    }

    _validateRequiredFields() {
        const errors = [];
        const form = this.elements.metadataForm;

        if (!form.uavType.value.trim()) {
            errors.push('UAV (тип дрона)');
            UI.setFieldValidation(form.uavType, false, 'Поле є обовʼязковим');
        } else {
            UI.setFieldValidation(form.uavType, true);
        }

        if (!form.videoContent.value.trim()) {
            errors.push('Контент відео');
            UI.setFieldValidation(form.videoContent, false, 'Поле є обовʼязковим');
        } else {
            UI.setFieldValidation(form.videoContent, true);
        }

        return errors;
    }

    _showJsonModal() {
        const jsonData = this._prepareJsonData();
        this.elements.modals.jsonContent.textContent = JSON.stringify(jsonData, null, 2);
        this.elements.modals.jsonModal.style.display = 'block';
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
        for (const project in this.state.projectFragments) {
            if (this.state.projectFragments[project].length > 0) {
                formattedProjects[project] = this.state.projectFragments[project].map((fragment, index) => ({
                    id: index,
                    start_time: fragment.start_formatted,
                    end_time: fragment.end_formatted
                }));
            }
        }

        return {
            azure_link: this.state.currentAzureLink,
            metadata: metadata,
            clips: formattedProjects
        };
    }

    async _saveFragments() {
        if (!this.elements.metadataForm.skipVideo.checked) {
            const validationErrors = this._validateRequiredFields();

            if (validationErrors.length > 0) {
                await showNotification(`Необхідно заповнити обовʼязкові поля:\n• ${validationErrors.join('\n• ')}`, 'error');
                return;
            }
        }

        let totalFragments = 0;
        for (const project in this.state.projectFragments) {
            totalFragments += this.state.projectFragments[project].length;
        }

        if (totalFragments === 0 && !this.elements.metadataForm.skipVideo.checked) {
            await showNotification('Немає фрагментів для збереження і відео не помічено як Skip', 'warning');
            return;
        }

        const unfinishedProjects = Object.keys(this.state.unfinishedFragments).filter(project =>
            this.state.unfinishedFragments[project] !== null
        );

        if (unfinishedProjects.length > 0) {
            const confirmed = await showConfirm('У вас є незавершені фрагменти, які не будуть збережені. Продовжити?');
            if (!confirmed) {
                return;
            }
        }

        const jsonData = this._prepareJsonData();

        try {
            const data = await Auth.authenticatedRequest('/save_fragments', {
                method: 'POST',
                body: JSON.stringify({
                    azure_link: this.state.currentAzureLink,
                    data: jsonData
                })
            });

            if (!data) return;

            if (data.success) {
                await showNotification(data.message || 'Дані успішно збережено в MongoDB.', 'success');
                if (data.task_id) {
                    console.log('Task ID:', data.task_id);
                }
            } else {
                await showNotification('Помилка: ' + data.error, 'error');
            }
        } catch (error) {
            const message = ErrorHandler.handleApiError(error, 'save_fragments');
            await showNotification(message, 'error');
        }
    }

    _closeModals() {
        this.elements.modals.jsonModal.style.display = 'none';
        this.elements.modals.projectModal.style.display = 'none';
    }

    _handleWindowClick(e) {
        if (e.target === this.elements.modals.jsonModal || e.target === this.elements.modals.projectModal) {
            this._closeModals();
        }
    }

    _getProjectName(projectKey) {
        const projectNames = {
            'motion-det': 'Motion Detection',
            'tracking': 'Tracking & Re-identification',
            'mil-hardware': 'Mil Hardware Detection',
            're-id': 'Re-ID'
        };
        return projectNames[projectKey] || projectKey;
    }
}

/**
 * Ініціалізація при завантаженні сторінки
 */
document.addEventListener('DOMContentLoaded', () => {
    window.videoAnnotator = new VideoAnnotator();
});