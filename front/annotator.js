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

// Завантаження списку відео при запуску сторінки
document.addEventListener('DOMContentLoaded', loadVideoList);

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

// Завантаження списку відео
function loadVideoList() {
    console.log("Запит списку відео...");
    fetch('/get_videos')
        .then(response => {
            console.log("Статус відповіді:", response.status);
            return response.json();
        })
        .then(data => {
            console.log("Отримані дані:", data);
            if (data.success && data.videos && data.videos.length > 0) {
                videoSelect.innerHTML = '<option value="">Виберіть відео...</option>';

                data.videos.forEach(video => {
                    console.log("Обробка відео в UI:", video);
                    const option = document.createElement('option');

                    // Використовуємо azure_link як значення для завантаження
                    option.value = video.azure_link;

                    // Видобуваємо назву файлу з local_path для відображення
                    let displayName;
                    if (video.local_path) {
                        const pathParts = video.local_path.split('/');
                        displayName = pathParts[pathParts.length - 1];
                    } else {
                        displayName = video.azure_link.split('/').pop() || `Відео #${video.id}`;
                    }

                    option.textContent = displayName;
                    option.dataset.id = video.id;
                    option.dataset.localPath = video.local_path || '';
                    videoSelect.appendChild(option);
                });
            } else {
                console.warn("Немає відео або помилка:", data);
                videoSelect.innerHTML = '<option value="">Немає доступних відео</option>';
            }
        })
        .catch(error => {
            console.error('Error loading videos:', error);
            videoSelect.innerHTML = '<option value="">Помилка завантаження відео</option>';
        });
}

// Обробник помилок відео
videoPlayer.addEventListener('error', function() {
    console.error('Помилка завантаження відео:', videoPlayer.error);

    // Показати повідомлення про помилку
    alert(`Помилка відтворення відео: ${videoPlayer.error ? videoPlayer.error.message : 'Невідома помилка'}`);

    // Альтернативне рішення - показати кнопку для повторної спроби
    const videoContainer = document.querySelector('.video-container');
    const errorMessage = document.createElement('div');
    errorMessage.className = 'video-error';
    errorMessage.innerHTML = `
        <p>Не вдалося завантажити відео. ${videoPlayer.error ? videoPlayer.error.message : ''}</p>
        <button class="btn" id="retry-video">Спробувати ще раз</button>
    `;

    videoContainer.appendChild(errorMessage);

    document.getElementById('retry-video').addEventListener('click', function() {
        videoPlayer.load();
        errorMessage.remove();
    });
});

// Обробник кнопки завантаження відео
loadVideoBtn.addEventListener('click', function() {
    const selectedVideo = videoSelect.value;
    if (!selectedVideo) {
        alert('Будь ласка, виберіть відео');
        return;
    }

    // Отримуємо назву файлу з тексту вибраної опції
    const selectedOption = videoSelect.options[videoSelect.selectedIndex];
    const azureLink = selectedOption.value;
    const filename = selectedOption.textContent;
    let localPath = selectedOption.dataset.localPath || '';

    // Перевіряємо правильність шляху до відео
    console.log(`Вибрано відео: azureLink=${azureLink}, localPath=${localPath}`);

    // Якщо шлях починається з source_videos, виправляємо його
    if (localPath.startsWith('source_videos/')) {
        const filename = localPath.split('/').pop();
        localPath = `/videos/${filename}`;
        console.log(`Виправлено шлях: ${localPath}`);
    }

    // Показуємо редактор і завантажуємо відео
    videoSelector.style.display = 'none';
    videoEditor.classList.remove('hidden');

    // Встановлюємо відео - використовуємо локальний шлях, якщо є
    if (localPath) {
        videoPlayer.src = localPath;
    } else {
        // Якщо немає локального шляху, спробуємо завантажити відео з Azure
        // Альтернативно, можна показати повідомлення про помилку
        alert('Відео не було завантажене локально. Спроба отримати відео напряму може не працювати.');
        videoPlayer.src = azureLink;
    }

    console.log(`Встановлено відео: ${videoPlayer.src}`);
    videoPlayer.load();

    // Відображаємо назву файлу
    videoFilenameSpan.textContent = filename;

    // Зберігаємо azure_link для наступних операцій
    currentAzureLink = azureLink;
    videoFileName = filename;

    // Очищаємо попередні дані
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

    // Завантажуємо існуючі анотації якщо вони є
    loadExistingAnnotations(azureLink);

    updateFragmentsList();
    clearAllMarkers();
    updateUnfinishedFragmentsUI();
    syncActiveProjects();
});

// Завантаження існуючих анотацій
function loadExistingAnnotations(azureLink) {
    fetch(`/get_annotation?azure_link=${encodeURIComponent(azureLink)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.annotation) {
                const annotation = data.annotation;

                // Заповнюємо метадані
                if (annotation.metadata) {
                    skipVideoCheckbox.checked = annotation.metadata.skip || false;
                    uavTypeSelect.value = annotation.metadata.uav_type || "";
                    videoContentSelect.value = annotation.metadata.video_content || "";
                    isUrbanCheckbox.checked = annotation.metadata.is_urban || false;
                    hasOsdCheckbox.checked = annotation.metadata.has_osd || false;
                    isAnalogCheckbox.checked = annotation.metadata.is_analog || false;
                    nightVideoCheckbox.checked = annotation.metadata.night_video || false;
                    multipleStreamsCheckbox.checked = annotation.metadata.multiple_streams || false;
                    hasInfantryCheckbox.checked = annotation.metadata.has_infantry || false;
                    hasExplosionsCheckbox.checked = annotation.metadata.has_explosions || false;
                }

                // Заповнюємо фрагменти
                if (annotation.clips) {
                    for (const projectType in annotation.clips) {
                        if (Array.isArray(annotation.clips[projectType])) {
                            projectFragments[projectType] = annotation.clips[projectType].map(clip => {
                                // Конвертуємо час у секунди для візуалізації
                                const startTimeParts = clip.start_time.split(':');
                                const endTimeParts = clip.end_time.split(':');

                                const startSeconds = parseInt(startTimeParts[0]) * 3600 +
                                                     parseInt(startTimeParts[1]) * 60 +
                                                     parseInt(startTimeParts[2]);

                                const endSeconds = parseInt(endTimeParts[0]) * 3600 +
                                                   parseInt(endTimeParts[1]) * 60 +
                                                   parseInt(endTimeParts[2]);

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

                    // Оновлюємо інтерфейс
                    updateFragmentsList();
                    visualizeFragments();
                }
            }
        })
        .catch(error => {
            console.error('Error loading annotations:', error);
        });
}

// Візуалізація фрагментів на таймлайні
function visualizeFragments() {
    clearAllMarkers();

    for (const projectType in projectFragments) {
        projectFragments[projectType].forEach(fragment => {
            const fragmentElement = document.createElement('div');
            fragmentElement.className = `fragment ${projectType}`;
            fragmentElement.dataset.id = fragment.id;
            fragmentElement.dataset.project = projectType;
            fragmentElement.style.left = `${(fragment.start / videoPlayer.duration) * 100}%`;
            fragmentElement.style.width = `${((fragment.end - fragment.start) / videoPlayer.duration) * 100}%`;
            fragmentElement.title = `${fragment.start_formatted} - ${fragment.end_formatted} (${getProjectName(projectType)})`;

            fragmentElement.addEventListener('click', function() {
                videoPlayer.currentTime = fragment.start;
                videoPlayer.play();
            });

            timeline.appendChild(fragmentElement);
        });
    }
}

// Синхронізуємо активні проєкти з чекбоксами
function syncActiveProjects() {
    activeProjects = [];
    projectCheckboxes.forEach(checkbox => {
        if (checkbox.checked) {
            activeProjects.push(checkbox.value);
        }
    });
    updateButtonStates();
}

// Функція оновлення стану кнопок
function updateButtonStates() {
    const noProjectsSelected = activeProjects.length === 0;
    // Не вимикаємо кнопку "Встановити початок фрагменту", щоб показувати алерт
    // startFragmentBtn.disabled = noProjectsSelected;

    const hasUnfinishedFragments = Object.values(unfinishedFragments).some(frag => frag !== null);
    // Кнопки "Завершити" і "Скасувати" будуть активні лише якщо є незавершені фрагменти
    endFragmentBtn.disabled = !hasUnfinishedFragments;
    cancelFragmentBtn.disabled = !hasUnfinishedFragments;
}

// JSON модальне вікно
viewJsonBtn.addEventListener('click', function() {
    // Форматуємо дані для відображення
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

    // Форматуємо дані проєктів для експорту
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

    // Збираємо JSON
    const jsonData = {
        azure_link: currentAzureLink,
        metadata: metadata,
        clips: formattedProjects
    };

    // Відображаємо JSON з форматуванням
    jsonContent.textContent = JSON.stringify(jsonData, null, 2);
    jsonModal.style.display = 'block';
});

// Синхронізуємо при завантаженні
document.addEventListener('DOMContentLoaded', syncActiveProjects);

// Обробники подій для відеоплеєра
videoPlayer.addEventListener('timeupdate', updateTimelineProgress);
videoPlayer.addEventListener('loadedmetadata', initVideoPlayer);

// Відеоплеєр
startFragmentBtn.addEventListener('click', function() {
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }
    setFragmentStart();
});

endFragmentBtn.addEventListener('click', function() {
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }
    showEndFragmentModal();
});

cancelFragmentBtn.addEventListener('click', function() {
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }
    showCancelFragmentModal();
});

saveFragmentsBtn.addEventListener('click', saveFragmentsToJson);

timeline.addEventListener('click', handleTimelineClick);

// Кнопки закриття модальних вікон
modalClose.forEach(function(closeBtn) {
    closeBtn.addEventListener('click', function() {
        jsonModal.style.display = 'none';
        projectModal.style.display = 'none';
    });
});

// Закриття модальних вікон при кліку поза ними
window.addEventListener('click', function(e) {
    if (e.target === jsonModal) {
        jsonModal.style.display = 'none';
    }
    if (e.target === projectModal) {
        projectModal.style.display = 'none';
    }
});

// Додаємо обробник зміни проєктів (чекбокси)
projectCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', function() {
        // Оновлюємо масив активних проєктів
        if (this.checked) {
            // Додаємо проєкт до активних, якщо його ще немає
            if (!activeProjects.includes(this.value)) {
                activeProjects.push(this.value);
            }
        } else {
            // Видаляємо проєкт з активних
            activeProjects = activeProjects.filter(p => p !== this.value);
        }

        // Оновлюємо стан кнопок
        updateButtonStates();
    });
});

// Вимикаємо форму для метаданих, якщо Skip
skipVideoCheckbox.addEventListener('change', function() {
    const metaFields = document.querySelectorAll('.meta-form .form-control, .meta-form input[type="checkbox"]:not(#skip-video)');
    metaFields.forEach(field => {
        field.disabled = this.checked;
    });
});

// Ініціалізація відео плеєра
function initVideoPlayer() {
    updateUnfinishedFragmentsUI();
    updateButtonStates();
    visualizeFragments();
}

// Оновлення прогресу на таймлайні
function updateTimelineProgress() {
    const progress = (videoPlayer.currentTime / videoPlayer.duration) * 100;
    timelineProgress.style.width = `${progress}%`;
}

// Клік на таймлайн
function handleTimelineClick(e) {
    const rect = timeline.getBoundingClientRect();
    const position = (e.clientX - rect.left) / rect.width;
    const time = position * videoPlayer.duration;

    videoPlayer.currentTime = time;
}

// Встановлення початку фрагменту для всіх активних проєктів
function setFragmentStart() {
    // Перевіряємо, чи вибраний хоча б один проєкт
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }

    const startTime = videoPlayer.currentTime;

    // Перевіряємо обрані проєкти
    for (const project of activeProjects) {
        // Якщо для проєкту вже є незавершений фрагмент, попереджаємо користувача
        if (unfinishedFragments[project]) {
            if (!confirm(`Для проєкту "${getProjectName(project)}" вже встановлена початкова мітка. Замінити її?`)) {
                continue; // Пропускаємо цей проєкт, якщо користувач не хоче замінювати мітку
            }

            // Видаляємо попередню мітку з таймлайну
            const oldMarker = document.querySelector(`.fragment-marker.start[data-project="${project}"]`);
            if (oldMarker) {
                timeline.removeChild(oldMarker);
            }
        }

        // Створюємо новий маркер для цього проєкту
        const marker = document.createElement('div');
        marker.className = `fragment-marker start ${project}`;
        marker.dataset.project = project;
        marker.style.left = `${(startTime / videoPlayer.duration) * 100}%`;
        marker.title = `${getProjectName(project)}: ${formatTime(startTime)}`;
        timeline.appendChild(marker);

        // Зберігаємо інформацію про незавершений фрагмент
        unfinishedFragments[project] = {
            start: startTime,
            start_formatted: formatTime(startTime)
        };
    }

    // Оновлюємо інтерфейс
    updateUnfinishedFragmentsUI();
}

// Оновлення інтерфейсу для незавершених фрагментів
function updateUnfinishedFragmentsUI() {
    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project => unfinishedFragments[project] !== null);

    // Активуємо/деактивуємо кнопки залежно від наявності незавершених фрагментів
    const hasUnfinished = unfinishedProjects.length > 0;
    endFragmentBtn.disabled = !hasUnfinished || activeProjects.length === 0;
    cancelFragmentBtn.disabled = !hasUnfinished || activeProjects.length === 0;

    // Оновлюємо панель статусу незавершених фрагментів
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

// Показати модальне вікно для вибору проєкту для завершення фрагменту
function showEndFragmentModal() {
    // Перевіряємо, чи вибраний хоча б один проєкт
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }

    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project =>
        unfinishedFragments[project] !== null && activeProjects.includes(project)
    );

    if (unfinishedProjects.length === 0) {
        alert('Немає незавершених фрагментів');
        return;
    }

    // Якщо є лише один незавершений фрагмент, використовуємо його без модального вікна
    if (unfinishedProjects.length === 1) {
        setFragmentEnd(unfinishedProjects[0]);
        return;
    }

    // Заповнюємо модальне вікно
    projectOptions.innerHTML = '';
    unfinishedProjects.forEach(project => {
        const option = document.createElement('div');
        option.className = `project-option ${project}`;
        option.textContent = `${getProjectName(project)} (початок: ${unfinishedFragments[project].start_formatted})`;
        option.addEventListener('click', function() {
            projectModal.style.display = 'none';
            setFragmentEnd(project);
        });
        projectOptions.appendChild(option);
    });

    // Показуємо модальне вікно
    projectModal.style.display = 'block';
}

// Показати модальне вікно для вибору проєкту для скасування фрагменту
function showCancelFragmentModal() {
    // Перевіряємо, чи вибраний хоча б один проєкт
    if (activeProjects.length === 0) {
        alert('Необхідно вибрати хоча б один проєкт');
        return;
    }

    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project =>
        unfinishedFragments[project] !== null && activeProjects.includes(project)
    );

    if (unfinishedProjects.length === 0) {
        alert('Немає незавершених фрагментів');
        return;
    }

    // Якщо є лише один незавершений фрагмент, використовуємо його без модального вікна
    if (unfinishedProjects.length === 1) {
        cancelFragment(unfinishedProjects[0]);
        return;
    }

    // Заповнюємо модальне вікно
    projectOptions.innerHTML = '';
    unfinishedProjects.forEach(project => {
        const option = document.createElement('div');
        option.className = `project-option ${project}`;
        option.textContent = `${getProjectName(project)} (початок: ${unfinishedFragments[project].start_formatted})`;
        option.addEventListener('click', function() {
            projectModal.style.display = 'none';
            cancelFragment(project);
        });
        projectOptions.appendChild(option);
    });

    // Показуємо модальне вікно
    projectModal.style.display = 'block';
}

// Встановлення кінця фрагменту для вказаного проєкту
function setFragmentEnd(project) {
    const endTime = videoPlayer.currentTime;

    // Перевіряємо наявність незавершеного фрагменту
    if (!unfinishedFragments[project]) {
        return;
    }

    // Перевіряємо, чи кінець після початку
    if (endTime <= unfinishedFragments[project].start) {
        alert('Кінець фрагменту має бути після початку');
        return;
    }

    // Створюємо повний фрагмент
    const completeFragment = {
        ...unfinishedFragments[project],
        end: endTime,
        end_formatted: formatTime(endTime),
        id: Date.now() + Math.floor(Math.random() * 1000),
        project: project
    };

    // Додаємо фрагмент до списку відповідного проєкту
    projectFragments[project].push(completeFragment);

    // Додаємо візуальний фрагмент на таймлайн
    const fragmentElement = document.createElement('div');
    fragmentElement.className = `fragment ${project}`;
    fragmentElement.dataset.id = completeFragment.id;
    fragmentElement.dataset.project = project;
    fragmentElement.style.left = `${(completeFragment.start / videoPlayer.duration) * 100}%`;
    fragmentElement.style.width = `${((completeFragment.end - completeFragment.start) / videoPlayer.duration) * 100}%`;
    fragmentElement.title = `${completeFragment.start_formatted} - ${completeFragment.end_formatted} (${getProjectName(project)})`;

    fragmentElement.addEventListener('click', function() {
        videoPlayer.currentTime = completeFragment.start;
        videoPlayer.play();
    });

    timeline.appendChild(fragmentElement);

    // Видаляємо початкову мітку для цього проєкту
    const startMarker = document.querySelector(`.fragment-marker.start[data-project="${project}"]`);
    if (startMarker) {
        timeline.removeChild(startMarker);
    }

    // Очищаємо дані незавершеного фрагменту
    unfinishedFragments[project] = null;

    // Оновлюємо інтерфейс
    updateUnfinishedFragmentsUI();
    updateFragmentsList();
}

// Скасування фрагменту для вказаного проєкту
function cancelFragment(project) {
    // Перевіряємо наявність незавершеного фрагменту
    if (!unfinishedFragments[project]) {
        return;
    }

    // Видаляємо початкову мітку для цього проєкту
    const startMarker = document.querySelector(`.fragment-marker.start[data-project="${project}"]`);
    if (startMarker) {
        timeline.removeChild(startMarker);
    }

    // Очищаємо дані незавершеного фрагменту
    unfinishedFragments[project] = null;

    // Оновлюємо інтерфейс
    updateUnfinishedFragmentsUI();
}

// Функція для отримання читабельного імені проєкту
function getProjectName(projectKey) {
    const projectNames = {
        'motion-det': 'Motion Detection',
        'tracking': 'Tracking & Re-identification',
        'mil-hardware': 'Mil Hardware Detection',
        're-id': 'Re-ID'
    };
    return projectNames[projectKey] || projectKey;
}

// Оновлення списку фрагментів
function updateFragmentsList() {
    fragmentsList.innerHTML = '';

    // Групуємо фрагменти за проєктами
    let totalFragments = 0;
    for (const project in projectFragments) {
        if (projectFragments[project].length > 0) {
            const projectHeader = document.createElement('h3');
            projectHeader.textContent = `${getProjectName(project)} (${projectFragments[project].length})`;
            fragmentsList.appendChild(projectHeader);

            projectFragments[project].forEach((fragment, index) => {
                const listItem = document.createElement('li');
                listItem.className = project;

                const timeInfo = document.createElement('span');
                timeInfo.textContent = `Фрагмент #${index + 1}: ${fragment.start_formatted} - ${fragment.end_formatted}`;

                const actions = document.createElement('div');

                const playBtn = document.createElement('button');
                playBtn.textContent = '▶';
                playBtn.className = 'btn';
                playBtn.addEventListener('click', function() {
                    videoPlayer.currentTime = fragment.start;
                    videoPlayer.play();

                    // Зупиняємо відео після фрагменту
                    const checkEnd = function() {
                        if (videoPlayer.currentTime >= fragment.end) {
                            videoPlayer.pause();
                            videoPlayer.removeEventListener('timeupdate', checkEnd);
                        }
                    };

                    videoPlayer.addEventListener('timeupdate', checkEnd);
                });

                const deleteBtn = document.createElement('button');
                deleteBtn.textContent = 'Видалити';
                deleteBtn.className = 'btn btn-danger';
                deleteBtn.addEventListener('click', function() {
                    // Видаляємо фрагмент зі списку
                    projectFragments[project] = projectFragments[project].filter(f => f.id !== fragment.id);

                    // Видаляємо візуальний фрагмент
                    const fragmentElement = document.querySelector(`.fragment[data-id="${fragment.id}"][data-project="${project}"]`);
                    if (fragmentElement) {
                        timeline.removeChild(fragmentElement);
                    }

                    // Оновлюємо список
                    updateFragmentsList();
                });

                actions.appendChild(playBtn);
                actions.appendChild(deleteBtn);

                listItem.appendChild(timeInfo);
                listItem.appendChild(actions);
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

// Видалення всіх маркерів
function clearAllMarkers() {
    const markers = timeline.querySelectorAll('.fragment, .fragment-marker');
    markers.forEach(marker => marker.remove());
}

// Збереження фрагментів у MongoDB
function saveFragmentsToJson() {
    // Перевіряємо, чи є фрагменти в будь-якому проєкті
    let totalFragments = 0;
    for (const project in projectFragments) {
        totalFragments += projectFragments[project].length;
    }

    if (totalFragments === 0 && !skipVideoCheckbox.checked) {
        alert('Немає фрагментів для збереження і відео не помічено як Skip');
        return;
    }

    // Перевіряємо, чи немає незавершених фрагментів
    const unfinishedProjects = Object.keys(unfinishedFragments).filter(project => unfinishedFragments[project] !== null);
    if (unfinishedProjects.length > 0) {
        if (!confirm('У вас є незавершені фрагменти, які не будуть збережені. Продовжити?')) {
            return;
        }
    }

    // Отримуємо метадані
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

    // Форматуємо дані проєктів для експорту - спрощена структура
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

    // Готуємо дані для відправки
    const jsonData = {
        metadata: metadata,
        clips: formattedProjects
    };

    // Змінений код для обробки відповіді
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
            alert('Дані успішно збережено в MongoDB. Запущено задачу обробки.');
            console.log('Task ID:', data.task_id);
        } else {
            alert('Помилка: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Помилка збереження даних');
    });
}

// Форматування часу (без мілісекунд)
function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    const hh = h.toString().padStart(2, '0');
    const mm = m.toString().padStart(2, '0');
    const ss = s.toString().padStart(2, '0');

    return `${hh}:${mm}:${ss}`;
}