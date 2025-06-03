// DOM елементи
const videoSelector = document.getElementById('video-selector');
const videoSelect = document.getElementById('video-select');
const loadVideoBtn = document.getElementById('load-video-btn');
const videoEditor = document.getElementById('video-editor');
const videoPlayer = document.getElementById('video-player');
const timeline = document.getElementById('timeline');
const timelineProgress = document.getElementById('timeline-progress');
const startFragmentBtn = document.getElementById('start-fragment');
const endFragmentBtn = document.getElementById('end-fragment');
const cancelFragmentBtn = document.getElementById('cancel-fragment');
const fragmentsList = document.getElementById('fragments-list');
const saveFragmentsBtn = document.getElementById('save-fragments');
const projectCheckboxes = document.querySelectorAll('input[name="project"]');
const videoFilenameSpan = document.querySelector('#video-filename span');
const unfinishedFragmentsStatus = document.getElementById('unfinished-fragments-status');

// Метадані форми
const skipVideoCheckbox = document.getElementById('skip-video');
const uavTypeSelect = document.getElementById('uav-type');
const videoContentSelect = document.getElementById('video-content');
const isUrbanCheckbox = document.getElementById('is-urban');
const hasOsdCheckbox = document.getElementById('has-osd');
const isAnalogCheckbox = document.getElementById('is-analog');
const nightVideoCheckbox = document.getElementById('night-video');
const multipleStreamsCheckbox = document.getElementById('multiple-streams');
const hasInfantryCheckbox = document.getElementById('has-infantry');
const hasExplosionsCheckbox = document.getElementById('has-explosions');

// JSON Modal
const viewJsonBtn = document.getElementById('view-json');
const jsonModal = document.getElementById('json-modal');
const jsonContent = document.getElementById('json-content');
const jsonModalClose = document.querySelector('#json-modal .modal-close');

// Project Modal
const projectModal = document.getElementById('project-modal');
const projectOptions = document.getElementById('project-options');
const modalClose = document.querySelectorAll('.modal-close');

// Змінні стану
let currentAzureLink = null;
let videoFileName = null;
let projectFragments = {
    'motion-det': [],
    'tracking': [],
    'mil-hardware': [],
    're-id': []
};
let unfinishedFragments = {
    'motion-det': null,
    'tracking': null,
    'mil-hardware': null,
    're-id': null
};
let activeProjects = [];

// Константи
const MIN_CLIP_DURATION = 1; // секунди

// Ініціалізація
document.addEventListener('DOMContentLoaded', init);

function init() {
    loadVideoList();
    setupEventListeners();
    syncActiveProjects();

    // Перевіряємо параметр video_id в URL
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('video_id');
    if (videoId) {
        selectVideoById(videoId);
    }
}

function setupEventListeners() {
    loadVideoBtn.addEventListener('click', handleLoadVideo);
    startFragmentBtn.addEventListener('click', handleStartFragment);
    endFragmentBtn.addEventListener('click', handleEndFragment);
    cancelFragmentBtn.addEventListener('click', handleCancelFragment);
    saveFragmentsBtn.addEventListener('click', saveFragmentsToJson);
    viewJsonBtn.addEventListener('click', showJsonModal);

    videoPlayer.addEventListener('timeupdate', updateTimelineProgress);
    videoPlayer.addEventListener('loadedmetadata', initVideoPlayer);
    videoPlayer.addEventListener('error', handleVideoError);

    timeline.addEventListener('click', handleTimelineClick);

    projectCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', syncActiveProjects);
    });

    skipVideoCheckbox.addEventListener('change', handleSkipChange);

    modalClose.forEach(closeBtn => {
        closeBtn.addEventListener('click', closeModals);
    });

    window.addEventListener('click', handleWindowClick);
}

function loadVideoList() {
    fetch('/get_videos')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.videos && data.videos.length > 0) {
                populateVideoSelect(data.videos);
            } else {
                videoSelect.innerHTML = '<option value="">Немає доступних відео</option>';
            }
        })
        .catch(error => {
            console.error('Error loading videos:', error);
            videoSelect.innerHTML = '<option value="">Помилка завантаження відео</option>';
        });
}

function populateVideoSelect(videos) {
    videoSelect.innerHTML = '<option value="">Виберіть відео...</option>';

    videos.forEach(video => {
        const option = document.createElement('option');
        option.value = video.azure_link;
        option.textContent = video.filename || video.azure_link.split('/').pop() || `Відео #${video.id}`;
        option.dataset.videoId = video.id;  // Використовуємо id замість _id
        option.dataset.filename = video.filename || '';
        option.dataset.azureLink = video.azure_link;
        videoSelect.appendChild(option);
    });
}

function selectVideoById(videoId) {
    const option = videoSelect.querySelector(`option[data-video-id="${videoId}"]`);
    if (option) {
        videoSelect.value = option.value;
        handleLoadVideo();
    } else {
        console.warn(`Відео з ID ${videoId} не знайдено в списку`);
    }
}

function handleLoadVideo() {
    const selectedVideo = videoSelect.value;
    if (!selectedVideo) {
        alert('Будь ласка, виберіть відео');
        return;
    }

    const selectedOption = videoSelect.options[videoSelect.selectedIndex];
    const azureLink = selectedOption.dataset.azureLink;
    const filename = selectedOption.dataset.filename || selectedOption.textContent;

    videoSelector.style.display = 'none';
    videoEditor.classList.remove('hidden');

    // Використовуємо локальний ендпоінт для отримання відео
    const videoUrl = `/get_video?azure_link=${encodeURIComponent(azureLink)}`;
    videoPlayer.src = videoUrl;
    videoPlayer.load();

    videoFilenameSpan.textContent = filename;

    currentAzureLink = azureLink;
    videoFileName = filename;

    resetFragments();
    loadExistingAnnotations(azureLink);
    updateFragmentsList();
    clearAllMarkers();
    updateUnfinishedFragmentsUI();
    syncActiveProjects();
}

function resetFragments() {
    projectFragments = {
        'motion-det': [],
        'tracking': [],
        'mil-hardware': [],
        're-id': []
    };

    unfinishedFragments = {
        'motion-det': null,
        'tracking': null,
        'mil-hardware': null,
        're-id': null
    };
}

function loadExistingAnnotations(azureLink) {
    fetch(`/get_annotation?azure_link=${encodeURIComponent(azureLink)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.annotation) {
                populateFormFromAnnotation(data.annotation);
                loadFragmentsFromAnnotation(data.annotation);
            }
        })
        .catch(error => console.error('Error loading annotations:', error));
}

function populateFormFromAnnotation(annotation) {
    if (annotation.metadata) {
        const metadata = annotation.metadata;
        skipVideoCheckbox.checked = metadata.skip || false;
        uavTypeSelect.value = metadata.uav_type || "";
        videoContentSelect.value = metadata.video_content || "";
        isUrbanCheckbox.checked = metadata.is_urban || false;
        hasOsdCheckbox.checked = metadata.has_osd || false;
        isAnalogCheckbox.checked = metadata.is_analog || false;
        nightVideoCheckbox.checked = metadata.night_video || false;
        multipleStreamsCheckbox.checked = metadata.multiple_streams || false;
        hasInfantryCheckbox.checked = metadata.has_infantry || false;
        hasExplosionsCheckbox.checked = metadata.has_explosions || false;
    }
}

function loadFragmentsFromAnnotation(annotation) {
    if (annotation.clips) {
        for (const projectType in annotation.clips) {
            if (Array.isArray(annotation.clips[projectType])) {
                projectFragments[projectType] = annotation.clips[projectType].map(clip => {
                    const startSeconds = timeStringToSeconds(clip.start_time);
                    const endSeconds = timeStringToSeconds(clip.end_time);

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
        updateFragmentsList();
        visualizeFragments();
    }
}

function timeStringToSeconds(timeString) {
    const parts = timeString.split(':');
    return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
}

function handleVideoError() {
    const errorMessage = videoPlayer.error ? videoPlayer.error.message : 'Невідома помилка';
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
        <p>Не вдалося завантажити відео: ${errorMessage}</p>
        <div style="margin-top: 15px;">
            <button class="btn btn-secondary" onclick="retryVideoLoad()">Спробувати ще раз</button>
        </div>
    `;

    videoContainer.appendChild(errorDiv);
}

function retryVideoLoad() {
    const errorDiv = document.querySelector('.video-error');
    if (errorDiv) {
        errorDiv.remove();
    }

    videoPlayer.load();
}

function syncActiveProjects() {
    activeProjects = [];
    projectCheckboxes.forEach(checkbox => {
        if (checkbox.checked) {
            activeProjects.push(checkbox.value);
        }
    });
    updateButtonStates();
}

function updateButtonStates() {
    const hasUnfinishedFragments = Object.values(unfinishedFragments).some(frag => frag !== null);
    endFragmentBtn.disabled = !hasUnfinishedFragments;
    cancelFragmentBtn.disabled = !hasUnfinishedFragments;
}

function handleStartFragment() {
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }
    setFragmentStart();
}

function handleEndFragment() {
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }
    showEndFragmentModal();
}

function handleCancelFragment() {
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }
    showCancelFragmentModal();
}

function setFragmentStart() {
    const startTime = videoPlayer.currentTime;

    for (const project of activeProjects) {
        if (unfinishedFragments[project]) {
            if (!confirm(`Для проєкту "${getProjectName(project)}" вже встановлена початкова мітка. Замінити її?`)) {
                continue;
            }

            const oldMarker = document.querySelector(`.fragment-marker.start[data-project="${project}"]`);
            if (oldMarker) {
                timeline.removeChild(oldMarker);
            }
        }

        const marker = document.createElement('div');
        marker.className = `fragment-marker start ${project}`;
        marker.dataset.project = project;
        marker.style.left = `${(startTime / videoPlayer.duration) * 100}%`;
        marker.title = `${getProjectName(project)}: ${formatTime(startTime)}`;
        timeline.appendChild(marker);

        unfinishedFragments[project] = {
            start: startTime,
            start_formatted: formatTime(startTime)
        };
    }

    updateUnfinishedFragmentsUI();
}

function showEndFragmentModal() {
    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project =>
        unfinishedFragments[project] !== null && activeProjects.includes(project)
    );

    if (unfinishedProjects.length === 0) {
        alert('Немає незавершених фрагментів');
        return;
    }

    if (unfinishedProjects.length === 1) {
        setFragmentEnd(unfinishedProjects[0]);
        return;
    }

    showProjectModal(unfinishedProjects, setFragmentEnd);
}

function showCancelFragmentModal() {
    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project =>
        unfinishedFragments[project] !== null && activeProjects.includes(project)
    );

    if (unfinishedProjects.length === 0) {
        alert('Немає незавершених фрагментів');
        return;
    }

    if (unfinishedProjects.length === 1) {
        cancelFragment(unfinishedProjects[0]);
        return;
    }

    showProjectModal(unfinishedProjects, cancelFragment);
}

function showProjectModal(projects, callback) {
    projectOptions.innerHTML = '';
    projects.forEach(project => {
        const option = document.createElement('div');
        option.className = `project-option ${project}`;
        option.textContent = `${getProjectName(project)} (початок: ${unfinishedFragments[project].start_formatted})`;
        option.addEventListener('click', function() {
            projectModal.style.display = 'none';
            callback(project);
        });
        projectOptions.appendChild(option);
    });

    projectModal.style.display = 'block';
}

function setFragmentEnd(project) {
    const endTime = videoPlayer.currentTime;

    if (!unfinishedFragments[project]) {
        return;
    }

    // Валідація мінімальної тривалості
    const duration = endTime - unfinishedFragments[project].start;
    if (duration < MIN_CLIP_DURATION) {
        const adjustedEndTime = unfinishedFragments[project].start + MIN_CLIP_DURATION;
        if (adjustedEndTime > videoPlayer.duration) {
            alert(`Неможливо створити кліп мінімальної тривалості ${MIN_CLIP_DURATION} сек. Недостатньо відео.`);
            return;
        }

        if (confirm(`Мінімальна тривалість кліпу - ${MIN_CLIP_DURATION} секунда. Автоматично збільшити до ${MIN_CLIP_DURATION} сек?`)) {
            videoPlayer.currentTime = adjustedEndTime;
            setFragmentEnd(project);
            return;
        } else {
            return;
        }
    }

    const completeFragment = {
        ...unfinishedFragments[project],
        end: endTime,
        end_formatted: formatTime(endTime),
        id: Date.now() + Math.floor(Math.random() * 1000),
        project: project
    };

    projectFragments[project].push(completeFragment);

    createFragmentVisualization(completeFragment);
    removeStartMarker(project);

    unfinishedFragments[project] = null;
    updateUnfinishedFragmentsUI();
    updateFragmentsList();
}

function createFragmentVisualization(fragment) {
    const fragmentElement = document.createElement('div');
    fragmentElement.className = `fragment ${fragment.project}`;
    fragmentElement.dataset.id = fragment.id;
    fragmentElement.dataset.project = fragment.project;
    fragmentElement.style.left = `${(fragment.start / videoPlayer.duration) * 100}%`;
    fragmentElement.style.width = `${((fragment.end - fragment.start) / videoPlayer.duration) * 100}%`;
    fragmentElement.title = `${fragment.start_formatted} - ${fragment.end_formatted} (${getProjectName(fragment.project)})`;

    fragmentElement.addEventListener('click', function() {
        videoPlayer.currentTime = fragment.start;
        videoPlayer.play();
    });

    timeline.appendChild(fragmentElement);
}

function removeStartMarker(project) {
    const startMarker = document.querySelector(`.fragment-marker.start[data-project="${project}"]`);
    if (startMarker) {
        timeline.removeChild(startMarker);
    }
}

function cancelFragment(project) {
    if (!unfinishedFragments[project]) {
        return;
    }

    removeStartMarker(project);
    unfinishedFragments[project] = null;
    updateUnfinishedFragmentsUI();
}

function updateUnfinishedFragmentsUI() {
    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project =>
        unfinishedFragments[project] !== null
    );

    const hasUnfinished = unfinishedProjects.length > 0;
    endFragmentBtn.disabled = !hasUnfinished || activeProjects.length === 0;
    cancelFragmentBtn.disabled = !hasUnfinished || activeProjects.length === 0;

    if (hasUnfinished) {
        let statusHTML = '<h3>Незавершені фрагменти:</h3>';
        unfinishedProjects.forEach(project => {
            statusHTML += `<div class="badge ${project}">${getProjectName(project)}: ${unfinishedFragments[project].start_formatted}</div>`;
        });
        unfinishedFragmentsStatus.innerHTML = statusHTML;
        unfinishedFragmentsStatus.style.display = 'block';
    } else {
        unfinishedFragmentsStatus.innerHTML = '';
        unfinishedFragmentsStatus.style.display = 'none';
    }
}

function updateFragmentsList() {
    fragmentsList.innerHTML = '';

    let totalFragments = 0;
    for (const project in projectFragments) {
        if (projectFragments[project].length > 0) {
            const projectHeader = document.createElement('h3');
            projectHeader.textContent = `${getProjectName(project)} (${projectFragments[project].length})`;
            fragmentsList.appendChild(projectHeader);

            projectFragments[project].forEach((fragment, index) => {
                const listItem = createFragmentListItem(fragment, index, project);
                fragmentsList.appendChild(listItem);
                totalFragments++;
            });
        }
    }

    if (totalFragments === 0) {
        const emptyMessage = document.createElement('p');
        emptyMessage.textContent = 'Немає фрагментів';
        fragmentsList.appendChild(emptyMessage);
    }
}

function createFragmentListItem(fragment, index, project) {
    const listItem = document.createElement('li');
    listItem.className = project;

    const timeInfo = document.createElement('span');
    timeInfo.textContent = `Фрагмент #${index + 1}: ${fragment.start_formatted} - ${fragment.end_formatted}`;

    const actions = document.createElement('div');

    const playBtn = document.createElement('button');
    playBtn.textContent = '▶';
    playBtn.className = 'btn';
    playBtn.addEventListener('click', () => playFragment(fragment));

    const deleteBtn = document.createElement('button');
    deleteBtn.textContent = 'Видалити';
    deleteBtn.className = 'btn btn-danger';
    deleteBtn.addEventListener('click', () => deleteFragment(fragment, project));

    actions.appendChild(playBtn);
    actions.appendChild(deleteBtn);

    listItem.appendChild(timeInfo);
    listItem.appendChild(actions);

    return listItem;
}

function playFragment(fragment) {
    videoPlayer.currentTime = fragment.start;
    videoPlayer.play();

    const checkEnd = function() {
        if (videoPlayer.currentTime >= fragment.end) {
            videoPlayer.pause();
            videoPlayer.removeEventListener('timeupdate', checkEnd);
        }
    };

    videoPlayer.addEventListener('timeupdate', checkEnd);
}

function deleteFragment(fragment, project) {
    projectFragments[project] = projectFragments[project].filter(f => f.id !== fragment.id);

    const fragmentElement = document.querySelector(`.fragment[data-id="${fragment.id}"][data-project="${project}"]`);
    if (fragmentElement) {
        timeline.removeChild(fragmentElement);
    }

    updateFragmentsList();
}

function visualizeFragments() {
    clearAllMarkers();

    for (const projectType in projectFragments) {
        projectFragments[projectType].forEach(fragment => {
            createFragmentVisualization(fragment);
        });
    }
}

function clearAllMarkers() {
    const markers = timeline.querySelectorAll('.fragment, .fragment-marker');
    markers.forEach(marker => marker.remove());
}

function initVideoPlayer() {
    updateUnfinishedFragmentsUI();
    updateButtonStates();
    visualizeFragments();
}

function updateTimelineProgress() {
    const progress = (videoPlayer.currentTime / videoPlayer.duration) * 100;
    timelineProgress.style.width = `${progress}%`;
}

function handleTimelineClick(e) {
    const rect = timeline.getBoundingClientRect();
    const position = (e.clientX - rect.left) / rect.width;
    const time = position * videoPlayer.duration;
    videoPlayer.currentTime = time;
}

function handleSkipChange() {
    const metaFields = document.querySelectorAll('.meta-form .form-control, .meta-form input[type="checkbox"]:not(#skip-video)');
    metaFields.forEach(field => {
        field.disabled = this.checked;
    });
}

function validateRequiredFields() {
    const errors = [];

    // Валідація UAV типу
    if (!uavTypeSelect.value.trim()) {
        errors.push('UAV (тип дрона)');
        uavTypeSelect.style.borderColor = '#e74c3c';
    } else {
        uavTypeSelect.style.borderColor = '';
    }

    // Валідація контенту відео
    if (!videoContentSelect.value.trim()) {
        errors.push('Контент відео');
        videoContentSelect.style.borderColor = '#e74c3c';
    } else {
        videoContentSelect.style.borderColor = '';
    }

    return errors;
}

function showJsonModal() {
    const jsonData = prepareJsonData();
    jsonContent.textContent = JSON.stringify(jsonData, null, 2);
    jsonModal.style.display = 'block';
}

function prepareJsonData() {
    const metadata = {
        skip: skipVideoCheckbox.checked,
        uav_type: uavTypeSelect.value,
        video_content: videoContentSelect.value,
        is_urban: isUrbanCheckbox.checked,
        has_osd: hasOsdCheckbox.checked,
        is_analog: isAnalogCheckbox.checked,
        night_video: nightVideoCheckbox.checked,
        multiple_streams: multipleStreamsCheckbox.checked,
        has_infantry: hasInfantryCheckbox.checked,
        has_explosions: hasExplosionsCheckbox.checked
    };

    const formattedProjects = {};
    for (const project in projectFragments) {
        if (projectFragments[project].length > 0) {
            formattedProjects[project] = projectFragments[project].map((fragment, index) => ({
                id: index,
                start_time: fragment.start_formatted,
                end_time: fragment.end_formatted
            }));
        }
    }

    return {
        azure_link: currentAzureLink,
        metadata: metadata,
        clips: formattedProjects
    };
}

function saveFragmentsToJson() {
    // Валідація обов'язкових полів (тільки якщо не skip)
    if (!skipVideoCheckbox.checked) {
        const validationErrors = validateRequiredFields();

        if (validationErrors.length > 0) {
            alert(`Необхідно заповнити обов'язкові поля:\n• ${validationErrors.join('\n• ')}`);
            return;
        }
    }

    let totalFragments = 0;
    for (const project in projectFragments) {
        totalFragments += projectFragments[project].length;
    }

    if (totalFragments === 0 && !skipVideoCheckbox.checked) {
        alert('Немає фрагментів для збереження і відео не помічено як Skip');
        return;
    }

    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project =>
        unfinishedFragments[project] !== null
    );

    if (unfinishedProjects.length > 0) {
        if (!confirm('У вас є незавершені фрагменти, які не будуть збережені. Продовжити?')) {
            return;
        }
    }

    const jsonData = prepareJsonData();

    fetch('/save_fragments', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            azure_link: currentAzureLink,
            data: jsonData
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message || 'Дані успішно збережено в MongoDB.');
            if (data.task_id) {
                console.log('Task ID:', data.task_id);
            }
        } else {
            alert('Помилка: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Помилка збереження даних');
    });
}

function closeModals() {
    jsonModal.style.display = 'none';
    projectModal.style.display = 'none';
}

function handleWindowClick(e) {
    if (e.target === jsonModal || e.target === projectModal) {
        closeModals();
    }
}

function getProjectName(projectKey) {
    const projectNames = {
        'motion-det': 'Motion Detection',
        'tracking': 'Tracking & Re-identification',
        'mil-hardware': 'Mil Hardware Detection',
        're-id': 'Re-ID'
    };
    return projectNames[projectKey] || projectKey;
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}