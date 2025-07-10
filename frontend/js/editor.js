class VideoEditor {
    constructor() {
        const requiredElements = [
            'video-editor',
            'video-player',
            'timeline',
            'timeline-progress',
            'start-fragment',
            'end-fragment',
            'cancel-fragment',
            'fragments-list',
            'save-annotation',
            'save-fragments',
            'video-filename',
            'unfinished-fragments-status',
            'video-lock-info',
            'lock-expires-time'
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
            currentAzureFilePath: null,
            currentVideoId: null,
            videoFileName: null,
            projectFragments: { 'motion_detection': [], 'military_targets_detection_and_tracking_moving': [], 'military_targets_detection_and_tracking_static': [], 're_id': [] },
            unfinishedFragments: { 'motion_detection': null, 'military_targets_detection_and_tracking_moving': null, 'military_targets_detection_and_tracking_static': null, 're_id': null },
            activeProjects: []
        };

        if (document.getElementById('project-modal')) {
            this.projectModal = new BaseModal('project-modal');
        }

        this._init();
    }

    _initElements() {
        const $ = id => document.getElementById(id);
        const elements = {
            videoEditor: $('video-editor'),
            videoPlayer: $('video-player'),
            timeline: $('timeline'),
            timelineProgress: $('timeline-progress'),
            startFragmentBtn: $('start-fragment'),
            endFragmentBtn: $('end-fragment'),
            cancelFragmentBtn: $('cancel-fragment'),
            fragmentsList: $('fragments-list'),
            saveAnnotationBtn: $('save-annotation'),
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
                hasExplosions: $('has-explosions')
            },

            videoWhere: $('video-where'),
            videoWhen: $('video-when'),
        };

        if (!elements.videoEditor) {
            console.error('Critical elements missing');
            return null;
        }

        return elements;
    }

    async _init() {
        if (!await auth.checkAccess()) return;

        const urlParams = new URLSearchParams(window.location.search);
        const videoId = urlParams.get('video_id');
        
        if (!videoId) {
            notify('ID відео не вказано', 'error');
            window.location.href = '/videos';
            return;
        }

        this._setupEvents();
        await this._loadVideoForAnnotation(videoId);
    }

    _setupEvents() {
        if (!this.elements) return;

        this.elements.startFragmentBtn?.addEventListener('click', () => this._handleStartFragment());
        this.elements.endFragmentBtn?.addEventListener('click', () => this._handleFragmentAction('end'));
        this.elements.cancelFragmentBtn?.addEventListener('click', () => this._handleFragmentAction('cancel'));
        this.elements.saveAnnotationBtn?.addEventListener('click', () => this._handleSaveAnnotation());
        this.elements.saveFragmentsBtn?.addEventListener('click', () => this._handleSaveFragments());

        this.elements.timeline?.addEventListener('click', e => this._handleTimelineClick(e));
        this.elements.metadataForm?.skipVideo?.addEventListener('change', () => this._handleSkipChange());
        
        // Add back button handler
        const backButton = document.getElementById('back-to-list');
        if (backButton) {
            backButton.addEventListener('click', async () => {
                if (this.state.currentVideoId) {
                    try {
                        await api.post(`/video/${this.state.currentVideoId}/unlock`);
                    } catch (error) {
                        console.error('Failed to unlock video:', error);
                    }
                }
                window.location.href = '/videos';
            });
        }

        this.elements.projectCheckboxes?.forEach(cb =>
            cb.addEventListener('change', () => this._syncActiveProjects())
        );

        // Валідація полів локації та дати
        this.elements.videoWhere?.addEventListener('input', (e) => this._validateLocationField(e));
        this.elements.videoWhere?.addEventListener('blur', (e) => this._cleanupLocationField(e));
        this.elements.videoWhen?.addEventListener('input', (e) => this._validateDateField(e));
        
    }

    async _loadVideoForAnnotation(videoId) {
        try {
            // Блокуємо відео
            const lockResult = await api.post(`/video/${videoId}/lock`);
            
            if (!lockResult?.success) {
                notify(lockResult?.message || 'Не вдалося заблокувати відео', 'error');
                window.location.href = '/videos';
                return;
            }

            // Отримуємо інформацію про відео після блокування
            const videoResponse = await api.get(`/video/list?page=1&per_page=100`);
            
            if (!videoResponse?.success) {
                notify('Не вдалося завантажити інформацію про відео', 'error');
                window.location.href = '/videos';
                return;
            }

            const video = videoResponse.videos.find(v => v.id === videoId);
            
            if (!video) {
                notify('Відео не знайдено', 'error');
                window.location.href = '/videos';
                return;
            }
            
            this.state.currentAzureFilePath = video.azure_file_path;
            this.state.currentVideoId = video.id;
            this.state.videoFileName = video.filename;
            this.elements.videoFilenameSpan.textContent = video.filename;

            // Показуємо інформацію про блокування з API відповіді
            if (lockResult.expires_at) {
                const expiresAt = new Date(lockResult.expires_at);
                this.elements.lockExpiresTime.textContent = expiresAt.toLocaleTimeString();
                this.elements.videoLockInfo.style.display = 'flex';
            } else {
                this.elements.videoLockInfo.style.display = 'none';
            }

            // Використовуємо новий безпечний endpoint з video_id замість Azure параметрів
            const videoUrl = `/video/${video.id}/stream?token=${auth.token}`;

            this._removeVideoEventListeners();
            this._addVideoEventListeners();

            this.elements.videoPlayer.src = videoUrl;
            this.elements.videoPlayer.load();

            this._resetFragments();
            
            // Завантажуємо існуючі анотації
            await this._loadExistingAnnotations(video.azure_file_path);
            
            this._updateFragmentsList();
            this._clearAllMarkers();
            this._updateUnfinishedFragmentsUI();
            this._syncActiveProjects();

        } catch (error) {
            console.error('Помилка завантаження відео для анотування:', error);
            notify('Помилка завантаження відео', 'error');
            window.location.href = '/videos';
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

    _handleVideoError(e) {
        console.error('Помилка відтворення відео:', e);
        notify('Помилка відтворення відео', 'error');
    }

    _initVideoPlayer() {
        this._updateTimelineProgress();
    }

    _updateTimelineProgress() {
        if (!this.elements.videoPlayer.duration) return;
        
        const progress = (this.elements.videoPlayer.currentTime / this.elements.videoPlayer.duration) * 100;
        this.elements.timelineProgress.style.width = `${progress}%`;
    }

    _handleTimelineClick(e) {
        const rect = this.elements.timeline.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const clickedTime = (x / rect.width) * this.elements.videoPlayer.duration;
        this.elements.videoPlayer.currentTime = clickedTime;
    }

    _validateLocationField(e) {
        // Дозволяємо тільки англійські літери, цифри та пробіли
        e.target.value = e.target.value.replace(/[^a-zA-Z0-9\s]/g, '');
    }

    _cleanupLocationField(e) {
        // При втраті фокусу замінюємо пробіли на підкреслення
        e.target.value = e.target.value.trim().replace(/\s+/g, '_');
    }

    _validateDateField(e) {
        // Дозволяємо тільки цифри
        e.target.value = e.target.value.replace(/\D/g, '');
        
        // Валідація дати при введенні
        if (e.target.value.length === 8) {
            const dateStr = e.target.value;
            const year = parseInt(dateStr.substring(0, 4));
            const month = parseInt(dateStr.substring(4, 6));
            const day = parseInt(dateStr.substring(6, 8));
            
            // Перевірка на правильність дати
            if (year < 1900 || year > 2100 || 
                month < 1 || month > 12 || 
                day < 1 || day > 31) {
                e.target.classList.add('error');
                return;
            }
            
            // Перевірка на правильність дня в місяці
            const date = new Date(year, month - 1, day);
            if (date.getFullYear() !== year || 
                date.getMonth() !== month - 1 || 
                date.getDate() !== day) {
                e.target.classList.add('error');
                return;
            }
            
            e.target.classList.remove('error');
        } else if (e.target.value.length > 0) {
            e.target.classList.remove('error');
        }
    }

    _handleSkipChange() {
        const isSkipped = this.elements.metadataForm.skipVideo.checked;
        
        // Вимикаємо/вмикаємо всі інші поля
        const fieldsToDisable = [
            ...this.elements.projectCheckboxes,
            this.elements.metadataForm.uavType,
            this.elements.metadataForm.videoContent,
            this.elements.metadataForm.isUrban,
            this.elements.metadataForm.hasOsd,
            this.elements.metadataForm.nightVideo,
            this.elements.metadataForm.multipleStreams,
            this.elements.metadataForm.hasExplosions,
            this.elements.videoWhere,
            this.elements.videoWhen,
            this.elements.startFragmentBtn,
            this.elements.endFragmentBtn,
            this.elements.cancelFragmentBtn
        ];
        
        fieldsToDisable.forEach(field => {
            if (field) field.disabled = isSkipped;
        });
        
        // Показуємо/приховуємо analog option в залежності від skip
        const analogOption = document.getElementById('analog-option');
        if (analogOption) {
            analogOption.style.display = isSkipped ? 'block' : 'none';
            // Скидаємо is_analog коли приховуємо
            if (!isSkipped && this.elements.metadataForm.isAnalog) {
                this.elements.metadataForm.isAnalog.checked = false;
            }
        }
        
        // Приховуємо/показуємо зірочки обов'язковості
        const uavRequired = document.getElementById('uav-required');
        const contentRequired = document.getElementById('content-required');
        if (uavRequired) uavRequired.style.display = isSkipped ? 'none' : 'inline';
        if (contentRequired) contentRequired.style.display = isSkipped ? 'none' : 'inline';
    }

    _resetFragments() {
        Object.assign(this.state, {
            projectFragments: { 'motion_detection': [], 'military_targets_detection_and_tracking_moving': [], 'military_targets_detection_and_tracking_static': [], 're_id': [] },
            unfinishedFragments: { 'motion_detection': null, 'military_targets_detection_and_tracking_moving': null, 'military_targets_detection_and_tracking_static': null, 're_id': null }
        });
    }

    _resetMetadataForm() {
        const form = this.elements.metadataForm;
        
        // Скидаємо всі чекбокси
        form.skipVideo.checked = false;
        form.isUrban.checked = false;
        form.hasOsd.checked = false;
        form.isAnalog.checked = false;
        form.nightVideo.checked = false;
        form.multipleStreams.checked = false;
        form.hasExplosions.checked = false;
        
        // Скидаємо селекти до значення за замовчуванням (першої опції)
        if (form.uavType.options.length > 0) {
            form.uavType.selectedIndex = 0;
        }
        if (form.videoContent.options.length > 0) {
            form.videoContent.selectedIndex = 0;
        }
        
        // Очищаємо текстові поля
        this.elements.videoWhere.value = '';
        this.elements.videoWhen.value = '';
        
        // Очищаємо помилки валідації
        const formElements = [form.uavType, form.videoContent, this.elements.videoWhere, this.elements.videoWhen];
        formElements.forEach(element => {
            if (element) {
                element.classList.remove('error');
            }
        });
        
        // Скидаємо вибір проєктів
        this.elements.projectCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        
        // Включаємо всі поля (відключаємо режим Skip)
        this._handleSkipChange();
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

        // where та when тепер в metadata
        if (metadata.where) this.elements.videoWhere.value = metadata.where;
        if (metadata.when) this.elements.videoWhen.value = metadata.when;

        const mappings = [
            [form.skipVideo, 'checked', metadata.skip || false],
            [form.uavType, 'value', metadata.uav_type || ""],
            [form.videoContent, 'value', metadata.video_content || ""],
            [form.isUrban, 'checked', metadata.is_urban || false],
            [form.hasOsd, 'checked', metadata.has_osd || false],
            [form.isAnalog, 'checked', metadata.is_analog || false],
            [form.nightVideo, 'checked', metadata.night_video || false],
            [form.multipleStreams, 'checked', metadata.multiple_streams || false],
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

        let finalEndTime = endTime;
        const duration = endTime - unfinished.start;
        
        if (duration < 1) {
            const adjustedEndTime = unfinished.start + 1;
            if (adjustedEndTime > this.elements.videoPlayer.duration) {
                return notify('Неможливо створити кліп мінімальної тривалості 1 сек. Недостатньо відео.', 'error');
            }

            const confirmed = await confirm('Мінімальна тривалість кліпу - 1 секунда. Автоматично збільшити до 1 сек?');
            if (confirmed) {
                finalEndTime = adjustedEndTime;
                this.elements.videoPlayer.currentTime = adjustedEndTime;
            } else {
                return; // Користувач скасував
            }
        }

        const completeFragment = {
            ...unfinished,
            end: finalEndTime,
            end_formatted: utils.formatTime(finalEndTime),
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
            emptyMessage.style.color = 'var(--text-secondary)';
            emptyMessage.style.textAlign = 'center';
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
        playBtn.addEventListener('click', () => this._playFragment(fragment.start, fragment.end));

        const deleteBtn = document.createElement('button');
        Object.assign(deleteBtn, { textContent: 'Видалити', className: 'btn btn-danger' });
        deleteBtn.addEventListener('click', () => this._deleteFragment(project, fragment.id));

        actions.append(playBtn, deleteBtn);
        listItem.append(timeInfo, actions);
        return listItem;
    }

    _playFragment(start, end) {
        this.elements.videoPlayer.currentTime = start;
        this.elements.videoPlayer.play();
        
        const checkEnd = setInterval(() => {
            if (this.elements.videoPlayer.currentTime >= end) {
                this.elements.videoPlayer.pause();
                clearInterval(checkEnd);
            }
        }, 100);
    }

    _deleteFragment(project, fragmentId) {
        const index = this.state.projectFragments[project].findIndex(f => f.id === fragmentId);
        if (index !== -1) {
            this.state.projectFragments[project].splice(index, 1);
            document.querySelector(`.fragment[data-id="${fragmentId}"]`)?.remove();
            this._updateFragmentsList();
        }
    }

    _visualizeFragments() {
        this._clearAllMarkers();
        Object.values(this.state.projectFragments).flat().forEach(fragment => {
            this._createFragmentVisualization(fragment);
        });
    }

    _clearAllMarkers() {
        this.elements.timeline.querySelectorAll('.fragment, .fragment-marker').forEach(el => el.remove());
    }

    _getProjectName(project) {
        const names = {
            'motion_detection': 'Motion Detection',
            'military_targets_detection_and_tracking_moving': 'Military Targets Moving',
            'military_targets_detection_and_tracking_static': 'Military Targets Static',
            're_id': 'Re-ID'
        };
        return names[project] || project;
    }

    async _handleSaveAnnotation() {
        try {
            const metadata = this._collectMetadata();
            const clips = this._collectClips();

            if (!this.elements.metadataForm.skipVideo.checked && Object.values(clips).every(arr => arr.length === 0)) {
                notify('Додайте хоча б один фрагмент або позначте відео як Skip', 'warning');
                return;
            }

            const annotationData = {
                azure_file_path: this.state.currentAzureFilePath,
                data: {
                    metadata,
                    clips
                }
            };

            // Якщо is_analog відмічено, додаємо video_source до даних
            if (this.elements.metadataForm.isAnalog?.checked) {
                annotationData.data.video_source = this.state.currentAzureFilePath;
            }

            console.log('Saving annotation with data:', JSON.stringify(annotationData, null, 2));
            const result = await api.post('/save_annotation', annotationData);
            if (result?.success) {
                notify('Анотацію збережено як чернетку', 'success');
            } else {
                notify(result?.message || 'Помилка збереження анотації', 'error');
            }
        } catch (error) {
            console.error('Помилка збереження анотації:', error);
            notify('Помилка збереження анотації', 'error');
        }
    }

    async _handleSaveFragments() {
        try {
            const metadata = this._collectMetadata();
            
            // Валідація обов'язкових полів (тільки якщо не skip)
            if (!metadata.skip && (!metadata.uav_type || !metadata.video_content)) {
                notify('Заповніть обов\'язкові поля: UAV тип та Контент відео', 'warning');
                
                // Підсвічуємо незаповнені обов'язкові поля
                if (!metadata.uav_type) this.elements.metadataForm.uavType.classList.add('error');
                if (!metadata.video_content) this.elements.metadataForm.videoContent.classList.add('error');
                
                return;
            }

            const clips = this._collectClips();

            if (!this.elements.metadataForm.skipVideo.checked && Object.values(clips).every(arr => arr.length === 0)) {
                notify('Додайте хоча б один фрагмент або позначте відео як Skip', 'warning');
                return;
            }

            const confirmed = await confirm('Завершити анотацію? Після збереження відео буде відправлено на обробку.');
            if (!confirmed) return;

            const annotationData = {
                azure_file_path: this.state.currentAzureFilePath,
                data: {
                    metadata,
                    clips
                }
            };

            const result = await api.post('/save_fragments', annotationData);
            
            if (result?.success) {
                notify('Анотацію завершено! Відео відправлено на обробку', 'success');
                
                // Розблоковуємо відео
                await api.post(`/video/${this.state.currentVideoId}/unlock`);
                
                // Повертаємось до списку відео
                setTimeout(() => {
                    window.location.href = '/videos';
                }, 1500);
            } else {
                notify(result?.message || 'Помилка збереження фрагментів', 'error');
            }
        } catch (error) {
            console.error('Помилка збереження фрагментів:', error);
            notify('Помилка збереження фрагментів', 'error');
        }
    }

    _collectMetadata() {
        const form = this.elements.metadataForm;
        return {
            skip: form.skipVideo.checked,
            uav_type: form.uavType.value,
            video_content: form.videoContent.value,
            is_urban: form.isUrban.checked,
            has_osd: form.hasOsd.checked,
            is_analog: form.isAnalog.checked,
            night_video: form.nightVideo.checked,
            multiple_streams: form.multipleStreams.checked,
            has_explosions: form.hasExplosions.checked,
            where: this.elements.videoWhere.value.trim(),
            when: this.elements.videoWhen.value.trim()
        };
    }

    _collectClips() {
        const clips = {};
        Object.entries(this.state.projectFragments).forEach(([project, fragments]) => {
            clips[project] = fragments.map((f, index) => ({
                id: index,
                start_time: f.start_formatted,
                end_time: f.end_formatted
            }));
        });
        return clips;
    }

    destroy() {
        this._removeVideoEventListeners();
        if (this.state.currentVideoId) {
            api.post(`/video/${this.state.currentVideoId}/unlock`).catch(console.error);
        }
    }
}

let videoEditor;

document.addEventListener('DOMContentLoaded', () => {
    videoEditor = new VideoEditor();
});

window.addEventListener('beforeunload', (e) => {
    if (videoEditor && videoEditor.state.currentVideoId) {
        // Спроба розблокувати відео при закритті сторінки
        navigator.sendBeacon(`/video/${videoEditor.state.currentVideoId}/unlock`, JSON.stringify({
            token: auth.token
        }));
    }
});