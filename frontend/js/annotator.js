class VideoAnnotator {
    constructor() {
        const requiredElements = [
            'videos-list-section',
            'video-editor',
            'videos-count-text',
            'status-filter',
            'videos-table-body',
            'pagination-container',
            'loading-status',
            'empty-state'
        ];

        const missingElements = requiredElements.filter(id => !document.getElementById(id));
        if (missingElements.length > 0) {
            console.error('Missing required elements:', missingElements);
            return;
        }

        this.elements = this._initElements();
        if (!this.elements) {
            console.error('Failed to initialize elements');
            return;
        }

        this._boundHandlers = {
            timeupdate: this._updateTimelineProgress.bind(this),
            loadedmetadata: this._initVideoPlayer.bind(this),
            error: this._handleVideoError.bind(this)
        };

        this.state = {
            currentPage: 1,
            perPage: 20,
            videos: [],
            pagination: {},
            filters: {
                status: ''
            },
            currentAzureFilePath: null,
            currentVideoId: null,
            videoFileName: null,
            projectFragments: { 'motion-det': [], 'tracking': [], 'mil-hardware': [], 're-id': [] },
            unfinishedFragments: { 'motion-det': null, 'tracking': null, 'mil-hardware': null, 're-id': null },
            activeProjects: [],
            renderedVideoIds: new Set(),
            isUnlocking: false
        };

        this.refreshInterval = null;

        if (document.getElementById('project-modal')) {
            this.projectModal = new BaseModal('project-modal');
        }

        this._init();
    }

    _initElements() {
        const $ = id => document.getElementById(id);
        const elements = {
            videosListSection: $('videos-list-section'),
            videoEditor: $('video-editor'),
            videosCountText: $('videos-count-text'),
            statusFilter: $('status-filter'),
            videosTableBody: $('videos-table-body'),
            paginationContainer: $('pagination-container'),
            loadingStatus: $('loading-status'),
            emptyState: $('empty-state'),

            backToListBtn: $('back-to-list-btn'),
            videoPlayer: $('video-player'),
            timeline: $('timeline'),
            timelineProgress: $('timeline-progress'),
            startFragmentBtn: $('start-fragment'),
            endFragmentBtn: $('end-fragment'),
            cancelFragmentBtn: $('cancel-fragment'),
            fragmentsList: $('fragments-list'),
            saveFragmentsBtn: $('save-fragments'),
            projectCheckboxes: document.querySelectorAll('input[name="project"]'),
            videoFilenameSpan: document.querySelector('#video-filename span'),
            unfinishedFragmentsStatus: $('unfinished-fragments-status'),
            videoLockInfo: $('video-lock-info'),
            lockExpiresTime: $('lock-expires-time'),

            metadataForm: {
                skipVideo: $('skip-video'),
                uavType: $('uav-type'),
                videoContent: $('video-content'),
                isUrban: $('is-urban'),
                hasOsd: $('has-osd'),
                isAnalog: $('is-analog'),
                nightVideo: $('night-video'),
                multipleStreams: $('multiple-streams'),
                hasInfantry: $('has-infantry'),
                hasExplosions: $('has-explosions')
            },

            videoWhere: $('video-where'),
            videoWhen: $('video-when'),
        };

        if (!elements.videosListSection || !elements.videoEditor) {
            console.error('Critical elements missing');
            return null;
        }

        return elements;
    }

    async _init() {
        if (!await auth.checkAccess()) return;

        this._setupEvents();
        await this._loadVideosList();
        this._startAutoRefresh();
    }

    _setupEvents() {
        if (!this.elements) return;

        this.elements.statusFilter?.addEventListener('change', () => this._applyFilters());

        this.elements.backToListBtn?.addEventListener('click', () => this._goBackToList());
        this.elements.startFragmentBtn?.addEventListener('click', () => this._handleStartFragment());
        this.elements.endFragmentBtn?.addEventListener('click', () => this._handleFragmentAction('end'));
        this.elements.cancelFragmentBtn?.addEventListener('click', () => this._handleFragmentAction('cancel'));
        this.elements.saveFragmentsBtn?.addEventListener('click', () => this._handleSaveFragments());

        this.elements.timeline?.addEventListener('click', e => this._handleTimelineClick(e));
        this.elements.metadataForm?.skipVideo?.addEventListener('change', () => this._handleSkipChange());

        this.elements.projectCheckboxes?.forEach(cb =>
            cb.addEventListener('change', () => this._syncActiveProjects())
        );
    }

    async _loadVideosList() {
        try {
            this._showLoading(true);

            const params = new URLSearchParams({
                page: this.state.currentPage.toString(),
                per_page: this.state.perPage.toString()
            });

            const data = await api.get(`/video/list?${params}`);

            if (data?.success) {
                this.state.videos = this._deduplicateVideos(data.videos);
                this.state.pagination = data.pagination;
                this._renderVideosList();
                this._renderPagination();
                this._updateVideosCount();
            } else {
                this._showEmptyState();
            }
        } catch (error) {
            console.error('Помилка завантаження відео:', error);
            notify('Помилка завантаження списку відео', 'error');
            this._showEmptyState();
        } finally {
            this._showLoading(false);
        }
    }

    _deduplicateVideos(videos) {
        const seen = new Set();
        const seenPaths = new Set();

        return videos.filter(video => {
            const pathKey = `${video.azure_file_path?.account_name}-${video.azure_file_path?.container_name}-${video.azure_file_path?.blob_path}`;

            if (seen.has(video.id) || seenPaths.has(pathKey)) {
                return false;
            }

            seen.add(video.id);
            seenPaths.add(pathKey);
            return true;
        });
    }

    _renderVideosList() {
        if (!this.state.videos.length) {
            this._showEmptyState();
            return;
        }

        const filteredVideos = this._applyFiltersToVideos();
        this._updateVideosTable(filteredVideos);
        this._showVideosList();
    }

    _updateVideosTable(videos) {
        const currentVideoIds = new Set(videos.map(v => v.id));
        const existingRows = this.elements.videosTableBody.querySelectorAll('tr[data-video-id]');

        existingRows.forEach(row => {
            const videoId = row.dataset.videoId;
            if (!currentVideoIds.has(videoId)) {
                row.remove();
                this.state.renderedVideoIds.delete(videoId);
            }
        });

        videos.forEach((video, index) => {
            const existingRow = this.elements.videosTableBody.querySelector(`tr[data-video-id="${video.id}"]`);

            if (existingRow) {
                this._updateVideoRow(existingRow, video);
            } else {
                const newRow = document.createElement('tr');
                newRow.dataset.videoId = video.id;
                newRow.innerHTML = this._createVideoRowContent(video);

                const nextRow = this.elements.videosTableBody.children[index];
                if (nextRow) {
                    this.elements.videosTableBody.insertBefore(newRow, nextRow);
                } else {
                    this.elements.videosTableBody.appendChild(newRow);
                }

                this.state.renderedVideoIds.add(video.id);
            }
        });
    }

    _updateVideoRow(row, video) {
        const lockStatus = video.lock_status || { locked: false };
        const canStart = video.can_start_work;
        const isLockedByMe = lockStatus.locked && lockStatus.user_id === this._getCurrentUserId();
        const isProcessing = ['downloading', 'in_progress', 'processing_clips'].includes(video.status);

        row.classList.toggle('processing-row', isProcessing);

        const statusBadge = row.querySelector('.status-badge');
        statusBadge.className = `status-badge ${video.status}`;
        statusBadge.textContent = this._getStatusLabel(video.status);

        const lockStatusCell = row.querySelector('.lock-status');
        lockStatusCell.innerHTML = `
            ${this._renderLockBadge(lockStatus, isLockedByMe)}
            ${lockStatus.locked && lockStatus.expires_in_seconds
                ? `<div class="lock-expires">Залишилось: ${this._formatTimeRemaining(lockStatus.expires_in_seconds)}</div>`
                : ''
            }
            ${lockStatus.locked && lockStatus.locked_at
                ? `<div class="lock-expires">Заблоковано: ${new Date(lockStatus.locked_at).toLocaleTimeString()}</div>`
                : ''
            }
        `;

        const actionsCell = row.querySelector('.video-actions');
        actionsCell.innerHTML = this._renderActionButtons(video, canStart, isLockedByMe);
    }

    _createVideoRowContent(video) {
        const lockStatus = video.lock_status || { locked: false };
        const canStart = video.can_start_work;
        const isLockedByMe = lockStatus.locked && lockStatus.user_id === this._getCurrentUserId();
        const isProcessing = ['downloading', 'in_progress', 'processing_clips'].includes(video.status);

        return `
            <td>
                <div class="video-filename" title="${utils.escapeHtml(video.filename)}">${utils.escapeHtml(video.filename)}</div>
            </td>
            <td>
                <span class="status-badge ${video.status}">${this._getStatusLabel(video.status)}</span>
            </td>
            <td>${this._formatDuration(video.duration_sec)}</td>
            <td>
                <div class="lock-status">
                    ${this._renderLockBadge(lockStatus, isLockedByMe)}
                    ${lockStatus.locked && lockStatus.expires_in_seconds
                        ? `<div class="lock-expires">Залишилось: ${this._formatTimeRemaining(lockStatus.expires_in_seconds)}</div>`
                        : ''
                    }
                    ${lockStatus.locked && lockStatus.locked_at
                        ? `<div class="lock-expires">Заблоковано: ${new Date(lockStatus.locked_at).toLocaleTimeString()}</div>`
                        : ''
                    }
                </div>
            </td>
            <td>
                <div class="video-actions">
                    ${this._renderActionButtons(video, canStart, isLockedByMe)}
                </div>
            </td>
        `;
    }

    _renderLockBadge(lockStatus, isLockedByMe) {
        if (!lockStatus.locked) {
            return '<span class="lock-badge free">🟢 Вільне</span>';
        }

        if (isLockedByMe) {
            return '<span class="lock-badge locked-by-me">🔵 Заблоковано вами</span>';
        }

        return `<span class="lock-badge locked">🔴 Заблоковано</span>
                <div style="font-size: 10px; color: var(--text-muted);">${lockStatus.locked_by}</div>`;
    }

    _renderActionButtons(video, canStart, isLockedByMe) {
        const buttons = [];

        if (canStart) {
            const buttonClass = isLockedByMe ? 'btn-start-work locked-by-me' : 'btn-start-work';
            const buttonText = isLockedByMe ? 'Продовжити роботу' : 'Почати роботу';
            buttons.push(
                `<button class="btn ${buttonClass}" onclick="videoAnnotator._startWork('${video.id}')">${buttonText}</button>`
            );
        } else {
            buttons.push(
                `<button class="btn btn-start-work" disabled>Недоступно</button>`
            );
        }

        if (isLockedByMe) {
            buttons.push(
                `<button class="btn-unlock" onclick="videoAnnotator._unlockVideo('${video.id}')" title="Розблокувати відео">🔓</button>`
            );
        }

        return buttons.join('');
    }

    async _startWork(videoId) {
        try {
            const video = this.state.videos.find(v => v.id === videoId);
            if (!video) return;

            const lockResult = await api.post(`/video/${videoId}/lock`, {});

            if (!lockResult.success) {
                notify(lockResult.error || lockResult.message, 'error');
                await this._refreshVideosList();
                return;
            }

            this.state.currentVideoId = videoId;

            video.lock_status = {
                locked: true,
                user_id: this._getCurrentUserId(),
                expires_in_seconds: 3600,
                locked_at: new Date().toISOString(),
                ...lockResult.lock_status
            };

            await this._loadVideoForAnnotation(video);

        } catch (error) {
            console.error('Помилка початку роботи:', error);

            if (error.message && error.message.includes('заблоковане')) {
                notify(error.message, 'warning');
            } else {
                notify('Помилка при блокуванні відео', 'error');
            }

            await this._refreshVideosList();
        }
    }

    async _unlockVideo(videoId) {
        if (!videoId) return;

        try {
            const confirmed = await confirm('Ви впевнені, що хочете розблокувати відео? Всі незбережені зміни будуть втрачені.');
            if (!confirmed) return;

            const result = await api.post(`/video/${videoId}/unlock`, {});

            if (result.success) {
                notify('Відео розблоковано', 'success');

                const video = this.state.videos.find(v => v.id === videoId);
                if (video) {
                    video.lock_status = { locked: false };
                }

                await this._refreshVideosList();
            } else {
                notify(result.error || 'Помилка розблокування відео', 'error');
            }

        } catch (error) {
            console.error('Помилка розблокування:', error);
            notify('Помилка розблокування відео', 'error');
        }
    }

    async _loadVideoForAnnotation(video) {
        try {
            this._stopAutoRefresh();

            this.elements.videosListSection.style.display = 'none';
            this.elements.videoEditor.classList.remove('hidden');

            this.state.currentAzureFilePath = video.azure_file_path;
            this.state.currentVideoId = video.id;
            this.state.videoFileName = video.filename;
            this.elements.videoFilenameSpan.textContent = video.filename;

            const lockStatus = video.lock_status;
            if (lockStatus && (lockStatus.expires_in_seconds || lockStatus.expires_at)) {
                let expiresAt;

                if (lockStatus.expires_in_seconds) {
                    expiresAt = new Date(Date.now() + lockStatus.expires_in_seconds * 1000);
                } else if (lockStatus.expires_at) {
                    expiresAt = new Date(lockStatus.expires_at);
                }

                if (expiresAt) {
                    this.elements.lockExpiresTime.textContent = expiresAt.toLocaleTimeString();
                    this.elements.videoLockInfo.style.display = 'flex';
                }
            }

            const params = new URLSearchParams();
            Object.entries(video.azure_file_path).forEach(([key, value]) => {
                params.append(key, value);
            });
            params.append('token', auth.token);

            const videoUrl = `/video/stream?${params}`;

            this._removeVideoEventListeners();
            this._addVideoEventListeners();

            this.elements.videoPlayer.src = videoUrl;
            this.elements.videoPlayer.load();

            this._resetFragments();
            await this._loadExistingAnnotations(video.azure_file_path);
            this._updateFragmentsList();
            this._clearAllMarkers();
            this._updateUnfinishedFragmentsUI();
            this._syncActiveProjects();

        } catch (error) {
            console.error('Помилка завантаження відео для анотування:', error);
            notify('Помилка завантаження відео', 'error');
            this._goBackToList();
        }
    }

    _addVideoEventListeners() {
        Object.entries(this._boundHandlers).forEach(([event, handler]) => {
            this.elements.videoPlayer.addEventListener(event, handler);
        });
    }

    _removeVideoEventListeners() {
        Object.entries(this._boundHandlers).forEach(([event, handler]) => {
            this.elements.videoPlayer.removeEventListener(event, handler);
        });
    }

    async _goBackToList() {
        try {
            if (this.state.isUnlocking) {
                return;
            }

            let needUnlock = false;

            if (this.state.currentVideoId) {
                const currentVideo = this.state.videos.find(v => v.id === this.state.currentVideoId);

                if (currentVideo && currentVideo.lock_status?.locked &&
                    currentVideo.lock_status.user_id === this._getCurrentUserId()) {
                    needUnlock = true;
                }
            }

            if (needUnlock) {
                try {
                    const result = await api.post(`/video/${this.state.currentVideoId}/unlock`, {});
                    if (result.success) {
                        console.log('Відео розблоковано при поверненні');
                    }
                } catch (error) {
                    console.error('Помилка розблокування:', error);
                }
            }

            this._removeVideoEventListeners();
            this.elements.videoPlayer.pause();
            this.elements.videoPlayer.src = '';
            this.elements.videoPlayer.load();

            this.elements.videoEditor.classList.add('hidden');
            this.elements.videosListSection.style.display = 'block';

            this.state.currentAzureFilePath = null;
            this.state.currentVideoId = null;
            this.state.videoFileName = null;
            this.elements.videoLockInfo.style.display = 'none';

            this._startAutoRefresh();
            await this._refreshVideosList();

        } catch (error) {
            console.error('Помилка повернення до списку:', error);
            notify('Помилка при поверненні до списку', 'error');

            this.elements.videoEditor.classList.add('hidden');
            this.elements.videosListSection.style.display = 'block';
            this.state.isUnlocking = false;
        }
    }

    _applyFiltersToVideos() {
        return this.state.videos.filter(video => {
            if (this.state.filters.status && video.status !== this.state.filters.status) {
                return false;
            }
            return true;
        });
    }

    _applyFilters() {
        this.state.filters.status = this.elements.statusFilter.value;
        this._renderVideosList();
    }

    _renderPagination() {
        if (!this.state.pagination.total_pages || this.state.pagination.total_pages <= 1) {
            this.elements.paginationContainer.innerHTML = '';
            return;
        }

        const { current_page, total_pages, has_prev, has_next } = this.state.pagination;

        let paginationHTML = `
            <button class="pagination-btn" ${!has_prev ? 'disabled' : ''}
                    onclick="videoAnnotator._changePage(${current_page - 1})">
                ← Попередня
            </button>
        `;

        const startPage = Math.max(1, current_page - 2);
        const endPage = Math.min(total_pages, current_page + 2);

        for (let page = startPage; page <= endPage; page++) {
            const isActive = page === current_page;
            paginationHTML += `
                <button class="pagination-btn ${isActive ? 'active' : ''}"
                        onclick="videoAnnotator._changePage(${page})">
                    ${page}
                </button>
            `;
        }

        paginationHTML += `
            <span class="pagination-info">
                Сторінка ${current_page} з ${total_pages}
            </span>
            <button class="pagination-btn" ${!has_next ? 'disabled' : ''}
                    onclick="videoAnnotator._changePage(${current_page + 1})">
                Наступна →
            </button>
        `;

        this.elements.paginationContainer.innerHTML = paginationHTML;
    }

    async _changePage(page) {
        if (page < 1 || page > this.state.pagination.total_pages) return;

        this.state.currentPage = page;
        await this._loadVideosList();
    }

    async _refreshVideosList() {
        try {
            const params = new URLSearchParams({
                page: this.state.currentPage.toString(),
                per_page: this.state.perPage.toString()
            });

            const data = await api.get(`/video/list?${params}`);

            if (data?.success) {
                this.state.videos = this._deduplicateVideos(data.videos);
                this.state.pagination = data.pagination;
                this._renderVideosList();
                this._renderPagination();
                this._updateVideosCount();
            }
        } catch (error) {
            console.error('Помилка оновлення списку відео:', error);
        }
    }

    _startAutoRefresh() {
        this.refreshInterval = setInterval(async () => {
            if (this.elements.videosListSection.style.display !== 'none') {
                try {
                    const params = new URLSearchParams({
                        page: this.state.currentPage.toString(),
                        per_page: this.state.perPage.toString()
                    });

                    const data = await api.get(`/video/list?${params}`);

                    if (data?.success) {
                        const oldVideosCount = this.state.videos.length;
                        const hasProcessingVideos = data.videos.some(v => v.status === 'processing_clips');

                        this.state.videos = this._deduplicateVideos(data.videos);
                        this.state.pagination = data.pagination;

                        if (oldVideosCount === 0 && this.state.videos.length > 0) {
                            this._renderVideosList();
                            this._renderPagination();
                            this._updateVideosCount();
                        } else if (this.state.videos.length > 0) {
                            const filteredVideos = this._applyFiltersToVideos();
                            this._updateVideosTable(filteredVideos);
                            this._updateVideosCount();
                        }

                        if (hasProcessingVideos && this.refreshInterval) {
                            clearInterval(this.refreshInterval);
                            this.refreshInterval = setInterval(() => this._startAutoRefresh(), 5000);
                        }
                    }
                } catch (error) {
                    console.error('Помилка автооновлення:', error);
                }
            }
        }, 5000);
    }

    _stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    _showLoading(show) {
        this.elements.loadingStatus.classList.toggle('hidden', !show);
        this.elements.videosTableBody.style.display = show ? 'none' : '';
    }

    _showEmptyState() {
        this.elements.emptyState.classList.remove('hidden');
        this.elements.videosTableBody.closest('.videos-table-container').style.display = 'none';
        this.elements.paginationContainer.innerHTML = '';
    }

    _showVideosList() {
        this.elements.emptyState.classList.add('hidden');
        this.elements.videosTableBody.closest('.videos-table-container').style.display = 'block';
    }

    _updateVideosCount() {
        const total = this.state.pagination.total_count || 0;
        this.elements.videosCountText.textContent = `Всього: ${total} відео`;
    }

    _getStatusLabel(status) {
        const labels = {
            'downloading': 'Завантаження',
            'not_annotated': 'Не анотоване',
            'in_progress': 'В процесі анотації',
            'processing_clips': 'Обробка кліпів',
            'annotated': 'Анотоване',
            'download_error': 'Помилка завантаження',
            'annotation_error': 'Помилка анотації'
        };
        return labels[status] || status;
    }

    _formatDuration(seconds) {
        if (!seconds) return '-';
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    _formatTimeRemaining(seconds) {
        if (!seconds || seconds <= 0) return 'Прострочено';

        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours}г ${minutes}хв`;
        }
        return `${minutes}хв`;
    }

    _getCurrentUserId() {
        try {
            const token = auth.token;
            if (!token) return null;
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.user_id;
        } catch {
            return null;
        }
    }

    _resetFragments() {
        Object.assign(this.state, {
            projectFragments: { 'motion-det': [], 'tracking': [], 'mil-hardware': [], 're-id': [] },
            unfinishedFragments: { 'motion-det': null, 'tracking': null, 'mil-hardware': null, 're-id': null }
        });
    }

    async _loadExistingAnnotations(azureFilePath) {
        try {
            const params = new URLSearchParams();
            Object.entries(azureFilePath).forEach(([key, value]) => {
                params.append(key, value);
            });

            const data = await api.get(`/get_annotation?${params}`);
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

        if (annotation.where) this.elements.videoWhere.value = annotation.where;
        if (annotation.when) this.elements.videoWhen.value = annotation.when;

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
        metaFields.forEach(field => {
            field.disabled = this.elements.metadataForm.skipVideo.checked;
            if (this.elements.metadataForm.skipVideo.checked) {
                field.classList.remove('error');
            }
        });
    }

    _handleVideoError(e) {
        if (!this.elements.videoPlayer.src ||
            this.elements.videoPlayer.src === '' ||
            this.elements.videoPlayer.src === window.location.href ||
            e.target.error?.code === MediaError.MEDIA_ERR_ABORTED) {
            return;
        }
        console.error('Помилка відтворення відео:', e);
        notify('Помилка відтворення відео', 'error');
    }

    _validateRequiredFields() {
        const form = this.elements.metadataForm;
        const errors = [];

        form.uavType.classList.remove('error');
        form.videoContent.classList.remove('error');

        if (!form.uavType.value.trim()) {
            errors.push('UAV (тип дрона)');
            form.uavType.classList.add('error');
        }
        if (!form.videoContent.value.trim()) {
            errors.push('Контент відео');
            form.videoContent.classList.add('error');
        }

        return errors;
    }

    _prepareJsonData() {
        const form = this.elements.metadataForm;
        const metadata = {
            skip: form.skipVideo.checked,
            where: this.elements.videoWhere.value.trim() || null,
            when: this.elements.videoWhen.value.trim() || null,
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
                notify(data.message || 'Анотацію успішно завершено. Відео відправлено на обробку.', 'success');

                // Розблоковуємо відео після успішного збереження
                if (this.state.currentVideoId) {
                    try {
                        await api.post(`/video/${this.state.currentVideoId}/unlock`, {});
                    } catch (error) {
                        console.error('Помилка розблокування після збереження:', error);
                    }
                }

                // Затримка для показу повідомлення, потім повертаємося до списку
                setTimeout(() => {
                    this._goBackToList();
                }, 1500);
            } else {
                notify('Помилка: ' + (data?.error || 'Невідома помилка'), 'error');
            }
        } catch (error) {
            notify(error.message, 'error');
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