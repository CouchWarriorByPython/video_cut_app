class VideosList {
    constructor() {
        const requiredElements = [
            'videos-list-section',
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

        this.state = {
            currentPage: 1,
            perPage: 20,
            videos: [],
            pagination: {},
            filters: {
                status: ''
            },
            renderedVideoIds: new Set(),
            isUnlocking: false
        };

        this.refreshInterval = null;
        this._init();
    }

    _initElements() {
        const $ = id => document.getElementById(id);
        const elements = {
            videosListSection: $('videos-list-section'),
            videosCountText: $('videos-count-text'),
            statusFilter: $('status-filter'),
            videosTableBody: $('videos-table-body'),
            paginationContainer: $('pagination-container'),
            loadingStatus: $('loading-status'),
            emptyState: $('empty-state')
        };

        if (!elements.videosListSection) {
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
            this._hideVideosTable();
            return;
        }

        const filteredVideos = this._applyFiltersToVideos();
        
        if (filteredVideos.length === 0) {
            this._showEmptyState();
            this._hideVideosTable();
            return;
        }
        
        this._showVideosTable();
        this._updateVideosTable(filteredVideos);
        this.state.renderedVideoIds = new Set(filteredVideos.map(v => v.id));
    }

    _applyFiltersToVideos() {
        let filteredVideos = [...this.state.videos];

        if (this.state.filters.status) {
            filteredVideos = filteredVideos.filter(video => video.status === this.state.filters.status);
        }

        return filteredVideos;
    }

    _updateVideosTable(videos) {
        if (!this.elements.videosTableBody) return;

        
        this.elements.videosTableBody.innerHTML = videos.map(video => {
            const isLocked = video.lock_status?.locked && video.lock_status.user_id !== api.userId;
            const canAnnotate = video.can_start_work;
            const isMyLock = video.lock_status?.locked && video.lock_status.user_id === api.userId;

            const isProcessing = ['downloading', 'in_progress', 'processing_clips'].includes(video.status);
            
            return `
                <tr class="video-row ${isLocked ? 'locked' : ''} ${isProcessing ? 'processing-row' : ''}">
                    <td>
                        <div class="video-filename" title="${this._escapeHtml(video.filename)}">
                            ${this._escapeHtml(video.filename)}
                        </div>
                    </td>
                    <td>
                        <span class="status-badge ${video.status}">
                            ${this._getStatusText(video.status)}
                        </span>
                    </td>
                    <td>${this._formatDuration(video.duration_sec)}</td>
                    <td>${this._renderLockInfo(video.lock_status)}</td>
                    <td>
                        <div class="video-actions">
                            ${canAnnotate && video.id ? `
                                <button class="btn btn-start-work ${isMyLock ? 'locked-by-me' : ''}" 
                                        onclick="window.location.href='/editor?video_id=${video.id}'">
                                    ${isMyLock ? 'Продовжити роботу' : 'Почати роботу'}
                                </button>
                            ` : `
                                <button class="btn btn-start-work" disabled>
                                    Недоступно
                                </button>
                            `}
                            ${isMyLock ? `
                                <button class="btn-unlock" 
                                        onclick="videosList._unlockVideo('${video.id}')"
                                        ${this.state.isUnlocking ? 'disabled' : ''}
                                        title="Розблокувати відео">
                                    🔓
                                </button>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        this._showEmptyState(videos.length === 0);
    }

    async _unlockVideo(videoId) {
        if (this.state.isUnlocking) return;

        try {
            this.state.isUnlocking = true;
            const data = await api.post(`/video/${videoId}/unlock`);
            
            if (data?.success) {
                notify('Відео розблоковано', 'success');
                await this._loadVideosList();
            } else {
                notify(data?.message || 'Помилка розблокування відео', 'error');
            }
        } catch (error) {
            console.error('Помилка розблокування:', error);
            notify('Помилка розблокування відео', 'error');
        } finally {
            this.state.isUnlocking = false;
        }
    }

    _renderPagination() {
        if (!this.elements.paginationContainer) return;
        
        const { current_page, total_pages, total_count } = this.state.pagination;
        
        // Ховаємо пагінацію якщо відео менше ніж per_page або тільки одна сторінка
        if (!total_pages || total_pages <= 1 || (total_count && total_count <= this.state.perPage)) {
            this.elements.paginationContainer.innerHTML = '';
            return;
        }
        let html = '<div class="pagination">';

        if (current_page > 1) {
            html += `<button class="btn btn-sm" onclick="videosList._changePage(${current_page - 1})">←</button>`;
        }

        const startPage = Math.max(1, current_page - 2);
        const endPage = Math.min(total_pages, current_page + 2);

        if (startPage > 1) {
            html += `<button class="btn btn-sm" onclick="videosList._changePage(1)">1</button>`;
            if (startPage > 2) html += '<span>...</span>';
        }

        for (let i = startPage; i <= endPage; i++) {
            const active = i === current_page ? 'btn-primary' : '';
            html += `<button class="btn btn-sm ${active}" onclick="videosList._changePage(${i})">${i}</button>`;
        }

        if (endPage < total_pages) {
            if (endPage < total_pages - 1) html += '<span>...</span>';
            html += `<button class="btn btn-sm" onclick="videosList._changePage(${total_pages})">${total_pages}</button>`;
        }

        if (current_page < total_pages) {
            html += `<button class="btn btn-sm" onclick="videosList._changePage(${current_page + 1})">→</button>`;
        }

        html += '</div>';
        this.elements.paginationContainer.innerHTML = html;
    }

    async _changePage(page) {
        this.state.currentPage = page;
        await this._loadVideosList();
    }

    _updateVideosCount() {
        if (!this.elements.videosCountText) return;

        const { total_count, current_page, per_page } = this.state.pagination;
        const total = total_count || 0;
        
        if (total === 0) {
            this.elements.videosCountText.textContent = 'Немає відео';
            return;
        }
        
        const start = (current_page - 1) * per_page + 1;
        const end = Math.min(current_page * per_page, total);

        this.elements.videosCountText.textContent = `${total} відео в базі`;
    }

    _applyFilters() {
        this.state.filters.status = this.elements.statusFilter?.value || '';
        this.state.currentPage = 1;
        this._loadVideosList();
    }

    _showLoading(show) {
        if (this.elements.loadingStatus) {
            this.elements.loadingStatus.classList.toggle('hidden', !show);
        }
        if (show) {
            this._hideVideosTable();
            this._showEmptyState(false);
            if (this.elements.videosTableBody) {
                this.elements.videosTableBody.innerHTML = '';
            }
        }
    }

    _showEmptyState(show = true) {
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.toggle('hidden', !show);
        }
    }

    _showVideosTable() {
        if (this.elements.videosTableBody) {
            const tableContainer = this.elements.videosTableBody.closest('.videos-table-container');
            if (tableContainer) {
                tableContainer.style.display = 'block';
            }
        }
        this._showEmptyState(false);
    }

    _hideVideosTable() {
        if (this.elements.videosTableBody) {
            const tableContainer = this.elements.videosTableBody.closest('.videos-table-container');
            if (tableContainer) {
                tableContainer.style.display = 'none';
            }
        }
    }

    _startAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        this.refreshInterval = setInterval(async () => {
            await this._loadVideosList();
        }, 5000);
    }

    _getStatusClass(status) {
        // Повертаємо оригінальні класи зі старого annotator.css
        return status || 'not_annotated';
    }

    _getStatusText(status) {
        const texts = {
            'downloading': 'Завантаження',
            'not_annotated': 'Не анотовано',
            'in_progress': 'В процесі анотації',
            'processing_clips': 'Обробка кліпів',
            'annotated': 'Анотовано',
            'download_error': 'Помилка завантаження',
            'annotation_error': 'Помилка анотації'
        };
        return texts[status] || 'Невідомо';
    }

    _formatDuration(seconds) {
        if (!seconds) return 'N/A';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    _renderLockInfo(lockStatus) {
        if (!lockStatus?.locked) {
            return '<span class="lock-badge free">🟢 Вільне</span>';
        }

        const isMyLock = lockStatus.user_id === api.userId;
        
        if (isMyLock) {
            return `
                <div class="lock-status">
                    <span class="lock-badge locked-by-me">🔵 Заблоковано вами</span>
                    ${this._getLockExpiresTime(lockStatus) ? `
                        <div class="lock-expires">До: ${this._getLockExpiresTime(lockStatus)}</div>
                    ` : ''}
                </div>
            `;
        }

        return `
            <div class="lock-status">
                <span class="lock-badge locked">🔴 Заблоковано</span>
                <div style="font-size: 10px; color: var(--text-muted);">${lockStatus.user_email || lockStatus.user_id}</div>
                ${this._getLockExpiresTime(lockStatus) ? `
                    <div class="lock-expires">До: ${this._getLockExpiresTime(lockStatus)}</div>
                ` : ''}
            </div>
        `;
    }

    _getLockExpiresTime(lockStatus) {
        if (!lockStatus || !lockStatus.locked) return null;

        let expiresAt = null;

        if (lockStatus.expires_in_seconds) {
            expiresAt = new Date(Date.now() + lockStatus.expires_in_seconds * 1000);
        } else if (lockStatus.expires_at) {
            expiresAt = new Date(lockStatus.expires_at);
        }

        return expiresAt ? expiresAt.toLocaleTimeString() : null;
    }

    async _unlockVideo(videoId) {
        if (!videoId) return;

        try {
            const confirmed = await confirm('Ви впевнені, що хочете розблокувати відео? Всі незбережені зміни будуть втрачені.');
            if (!confirmed) return;

            this.state.isUnlocking = true;
            
            const result = await api.post(`/video/${videoId}/unlock`, {});

            if (result.success) {
                notify('Відео розблоковано', 'success');

                const video = this.state.videos.find(v => v.id === videoId);
                if (video) {
                    video.lock_status = { locked: false };
                }

                await this._loadVideosList();
            } else {
                notify(result.error || 'Помилка розблокування відео', 'error');
            }

        } catch (error) {
            console.error('Помилка розблокування:', error);
            notify('Помилка розблокування відео', 'error');
        } finally {
            this.state.isUnlocking = false;
        }
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
}

let videosList;

document.addEventListener('DOMContentLoaded', () => {
    videosList = new VideosList();
});

window.addEventListener('beforeunload', () => {
    if (videosList) {
        videosList.destroy();
    }
});