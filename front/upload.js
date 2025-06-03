const videoUrlInput = document.getElementById('video-url');
const metadataWhereInput = document.getElementById('metadata-where');
const metadataWhenInput = document.getElementById('metadata-when');
const uploadBtn = document.getElementById('upload-btn');
const resultDiv = document.getElementById('result');

let lastUploadedVideoId = null;
let lastUploadedAzureLink = null;
let statusCheckInterval = null;

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

    showLoading(url);

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
        if (data.success) {
            lastUploadedVideoId = data.id;
            lastUploadedAzureLink = data.azure_link;
            resetForm();
            startStatusChecking(data.azure_link);
        }
    })
    .catch(error => {
        console.error('Помилка:', error);
        showError(`Помилка з'єднання з сервером: ${error.message}`);
    });
}

function handleUploadResponse(data) {
    if (data.success) {
        showProcessing({
            message: data.message || `Відео ${data.filename} успішно зареєстровано`,
            azure_link: data.azure_link,
            filename: data.filename,
            id: data.id,
            conversion_task_id: data.conversion_task_id
        });
    } else {
        showError(data.message || 'Невідома помилка при реєстрації відео');
    }
}

function startStatusChecking(azureLink) {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }

    statusCheckInterval = setInterval(() => {
        checkVideoStatus(azureLink);
    }, 2000);
}

function checkVideoStatus(azureLink) {
    fetch(`/video_status?azure_link=${encodeURIComponent(azureLink)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateStatusDisplay(data);

                if (data.ready_for_annotation) {
                    clearInterval(statusCheckInterval);
                    showSuccess({
                        message: `Відео ${data.filename} готове до анотування`,
                        azure_link: azureLink,
                        filename: data.filename,
                        id: lastUploadedVideoId
                    });
                } else if (data.status === 'conversion_failed') {
                    clearInterval(statusCheckInterval);
                    showError('Помилка конвертації відео. Спробуйте завантажити інше відео.');
                }
            }
        })
        .catch(error => {
            console.error('Помилка перевірки статусу:', error);
        });
}

function updateStatusDisplay(statusData) {
    const statusMessages = {
        'processing': 'Завантаження з Azure Storage...',
        'converting': 'Конвертація відео для браузера...',
        'ready': 'Відео готове до анотування',
        'conversion_failed': 'Помилка конвертації відео'
    };

    const currentMessage = statusMessages[statusData.status] || 'Обробка відео...';

    const existingResult = resultDiv.querySelector('.info-message');
    if (existingResult) {
        const statusElement = existingResult.querySelector('.status-text');
        if (statusElement) {
            statusElement.textContent = currentMessage;
        }
    }
}

function showLoading(url) {
    resultDiv.innerHTML = `
        <div class="info-message">
            <h3>Завантаження відео...</h3>
            <p>Завантажуємо відео з Azure Storage локально:</p>
            <p class="url-display">${url}</p>
            <div class="loading-spinner"></div>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Завантажуємо...';
}

function showProcessing(data) {
    resultDiv.innerHTML = `
        <div class="info-message">
            <h3>Обробка відео</h3>
            <p><strong>Файл:</strong> ${data.filename}</p>
            <p><strong>ID:</strong> ${data.id}</p>
            <p class="status-text">Завантаження з Azure Storage...</p>
            <div class="loading-spinner"></div>
            <div class="video-info">
                <p><strong>Azure посилання:</strong></p>
                <p class="url-display">${data.azure_link}</p>
            </div>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
}

function resetForm() {
    metadataWhereInput.value = '';
    metadataWhenInput.value = '';
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
    videoUrlInput.style.borderColor = '';
}

function showSuccess(data) {
    resultDiv.innerHTML = `
        <div class="success-message">
            <h3>Відео готове!</h3>
            <p>${data.message}</p>
            <div class="video-info">
                <p><strong>Файл:</strong> ${data.filename}</p>
                <p><strong>ID:</strong> ${data.id}</p>
                <p><strong>Azure посилання:</strong></p>
                <p class="url-display">${data.azure_link}</p>
            </div>
            <div style="margin-top: 15px;">
                <button class="btn btn-success full-width" onclick="window.location.href='/annotator?video_id=${data.id}'">
                    Перейти до анотування
                </button>
            </div>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
}

function showError(message) {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }

    resultDiv.innerHTML = `
        <div class="error-message">
            <h3>Помилка реєстрації</h3>
            <p>${message}</p>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
}