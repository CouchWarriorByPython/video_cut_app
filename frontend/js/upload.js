const videoUrlInput = document.getElementById('video-url');
const metadataWhereInput = document.getElementById('metadata-where');
const metadataWhenInput = document.getElementById('metadata-when');
const uploadBtn = document.getElementById('upload-btn');
const resultDiv = document.getElementById('result');

let activeUploads = new Map(); // Map для зберігання активних завантажень
let progressIntervals = new Map(); // Map для intervals

// Завантажуємо збережені завантаження при ініціалізації
document.addEventListener('DOMContentLoaded', function() {
    loadSavedUploads();
});

uploadBtn.addEventListener('click', handleUpload);
videoUrlInput.addEventListener('input', validateAzureUrl);

function validateAzureUrl() {
    const url = videoUrlInput.value.trim();

    if (!url) {
        videoUrlInput.style.borderColor = '';
        return;
    }

    const isValid = isValidAzureUrl(url);
    videoUrlInput.style.borderColor = isValid ? '#2ecc71' : '#e74c3c';
}

function isValidAzureUrl(url) {
    try {
        const urlObj = new URL(url);
        return urlObj.hostname.includes('.blob.core.windows.net') &&
               urlObj.pathname.length > 1;
    } catch {
        return false;
    }
}

function handleUpload() {
    const url = videoUrlInput.value.trim();
    const where = metadataWhereInput.value.trim();
    const when = metadataWhenInput.value.trim();

    if (!url) {
        showError('Будь ласка, вкажіть Azure Blob URL відео');
        return;
    }

    if (!isValidAzureUrl(url)) {
        showError('Некоректний Azure Blob URL. Використовуйте формат: https://account.blob.core.windows.net/container/path/file.mp4');
        return;
    }

    if (where && !/^[A-Za-z\s\-_]+$/.test(where)) {
        showError('Локація може містити тільки англійські літери, пробіли, дефіси та підкреслення');
        return;
    }

    if (when && !/^\d{8}$/.test(when)) {
        showError('Дата повинна бути у форматі РРРРММДД (8 цифр)');
        return;
    }

    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Реєструємо...';

    fetch('/upload', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            video_url: url,
            where: where || null,
            when: when || null
        }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP помилка! Статус: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("Отримана відповідь:", data);
        handleUploadResponse(data);
        resetForm();
    })
    .catch(error => {
        console.error('Помилка:', error);
        showError(`Помилка з'єднання з сервером: ${error.message}`);
        resetForm();
    });
}

function handleUploadResponse(data) {
    if (data.success) {
        const uploadId = generateUploadId();
        const uploadData = {
            id: uploadId,
            taskId: data.conversion_task_id,
            azure_link: data.azure_link,
            filename: data.filename,
            message: data.message,
            timestamp: Date.now()
        };

        // Зберігаємо в activeUploads та localStorage
        activeUploads.set(uploadId, uploadData);
        saveUploadsToStorage();

        // Показуємо прогрес-бар
        showProgressBar(uploadData);

        // Починаємо відстеження прогресу
        startProgressTracking(uploadId);
    } else {
        showError(data.message || 'Невідома помилка при реєстрації відео');
    }
}

function showProgressBar(uploadData) {
    const progressId = `progress-${uploadData.id}`;

    const progressHTML = `
        <div id="${progressId}" class="upload-progress-item">
            <div class="upload-info">
                <h3>Обробка відео</h3>
                <p><strong>Файл:</strong> ${uploadData.filename}</p>
                <p><strong>Azure посилання:</strong></p>
                <p class="url-display">${uploadData.azure_link}</p>
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
                <button class="btn btn-secondary" onclick="removeUpload('${uploadData.id}')">Приховати</button>
            </div>
        </div>
    `;

    // Додаємо до результатів або замінюємо існуючий
    if (resultDiv.children.length === 0) {
        resultDiv.innerHTML = progressHTML;
    } else {
        resultDiv.insertAdjacentHTML('afterbegin', progressHTML);
    }

    resultDiv.classList.remove('hidden');
}

function startProgressTracking(uploadId) {
    const uploadData = activeUploads.get(uploadId);
    if (!uploadData) return;

    const interval = setInterval(() => {
        checkTaskProgress(uploadId);
    }, 2000); // Перевіряємо кожні 2 секунди

    progressIntervals.set(uploadId, interval);
}

function checkTaskProgress(uploadId) {
    const uploadData = activeUploads.get(uploadId);
    if (!uploadData) {
        clearProgressInterval(uploadId);
        return;
    }

    fetch(`/task_status/${uploadData.taskId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            updateProgressDisplay(uploadId, data);

            if (data.status === 'completed' || data.status === 'failed') {
                clearProgressInterval(uploadId);

                if (data.status === 'completed') {
                    showCompletedState(uploadId, uploadData);
                } else {
                    showErrorState(uploadId, data.message);
                }
            }
        })
        .catch(error => {
            console.error('Помилка перевірки прогресу:', error);
            // Видаляємо неіснуючу задачу
            removeUpload(uploadId);
        });
}

function updateProgressDisplay(uploadId, progressData) {
    const progressElement = document.getElementById(`progress-${uploadId}`);
    if (!progressElement) return;

    const statusText = progressElement.querySelector('.status-text');
    const progressPercentage = progressElement.querySelector('.progress-percentage');
    const progressFill = progressElement.querySelector('.progress-fill');
    const progressStage = progressElement.querySelector('.progress-stage');

    const progress = progressData.progress || 0;
    const stage = progressData.stage || 'unknown';
    const message = progressData.message || 'Обробка...';

    // Оновлюємо текст статусу
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

    // Змінюємо колір в залежності від етапу
    progressFill.className = 'progress-fill';
    if (stage === 'downloading') {
        progressFill.classList.add('downloading');
    } else if (stage === 'converting') {
        progressFill.classList.add('converting');
    } else if (stage === 'completed') {
        progressFill.classList.add('completed');
    } else if (stage === 'failed') {
        progressFill.classList.add('failed');
    }
}

function showCompletedState(uploadId, uploadData) {
    const progressElement = document.getElementById(`progress-${uploadId}`);
    if (!progressElement) return;

    const actionsDiv = progressElement.querySelector('.upload-actions');
    actionsDiv.innerHTML = `
        <button class="btn btn-success" onclick="window.location.href='/annotator?azure_link=${encodeURIComponent(uploadData.azure_link)}'">
            Перейти до анотування
        </button>
        <button class="btn btn-secondary" onclick="removeUpload('${uploadId}')">Приховати</button>
    `;

    // Видаляємо з активних завантажень
    activeUploads.delete(uploadId);
    saveUploadsToStorage();
}

function showErrorState(uploadId, errorMessage) {
    const progressElement = document.getElementById(`progress-${uploadId}`);
    if (!progressElement) return;

    const progressStage = progressElement.querySelector('.progress-stage');
    progressStage.innerHTML = `<span style="color: #e74c3c;">Помилка: ${errorMessage}</span>`;

    // Видаляємо з активних завантажень
    activeUploads.delete(uploadId);
    saveUploadsToStorage();
}

function removeUpload(uploadId) {
    clearProgressInterval(uploadId);
    activeUploads.delete(uploadId);
    saveUploadsToStorage();

    const progressElement = document.getElementById(`progress-${uploadId}`);
    if (progressElement) {
        progressElement.remove();
    }

    // Якщо немає більше завантажень, ховаємо весь блок результатів
    if (resultDiv.children.length === 0) {
        resultDiv.classList.add('hidden');
    }
}

function clearProgressInterval(uploadId) {
    const interval = progressIntervals.get(uploadId);
    if (interval) {
        clearInterval(interval);
        progressIntervals.delete(uploadId);
    }
}

function generateUploadId() {
    return 'upload_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function saveUploadsToStorage() {
    const uploadsArray = Array.from(activeUploads.values());
    localStorage.setItem('activeUploads', JSON.stringify(uploadsArray));
}

async function validateTaskExists(taskId) {
    try {
        const response = await fetch(`/task_status/${taskId}`);
        return response.ok;
    } catch (error) {
        return false;
    }
}

async function loadSavedUploads() {
    try {
        const saved = localStorage.getItem('activeUploads');
        if (saved) {
            const uploadsArray = JSON.parse(saved);

            for (const uploadData of uploadsArray) {
                const hoursSinceUpload = (Date.now() - uploadData.timestamp) / (1000 * 60 * 60);

                // Перевіряємо чи не застаріла задача та чи існує вона в системі
                if (hoursSinceUpload < 24) {
                    const taskExists = await validateTaskExists(uploadData.taskId);
                    if (taskExists) {
                        activeUploads.set(uploadData.id, uploadData);
                        showProgressBar(uploadData);
                        startProgressTracking(uploadData.id);
                    }
                }
            }

            if (activeUploads.size > 0) {
                resultDiv.classList.remove('hidden');
            }

            // Оновлюємо localStorage, видаляючи неактуальні записи
            saveUploadsToStorage();
        }
    } catch (error) {
        console.error('Помилка завантаження збережених завантажень:', error);
        localStorage.removeItem('activeUploads');
    }
}

function resetForm() {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
    videoUrlInput.style.borderColor = '';
}

function showError(message) {
    resultDiv.innerHTML = `
        <div class="error-message">
            <h3>Помилка реєстрації</h3>
            <p>${message}</p>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    resetForm();
}