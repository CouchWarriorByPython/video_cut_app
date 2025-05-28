// DOM елементи
const videoUrlInput = document.getElementById('video-url');
const metadataWhereInput = document.getElementById('metadata-where');
const metadataWhenInput = document.getElementById('metadata-when');
const uploadBtn = document.getElementById('upload-btn');
const resultDiv = document.getElementById('result');

// Обробники подій
uploadBtn.addEventListener('click', handleUpload);
videoUrlInput.addEventListener('input', validateAzureUrl);

// Валідація Azure URL в реальному часі
function validateAzureUrl() {
    const url = videoUrlInput.value.trim();

    if (!url) {
        videoUrlInput.style.borderColor = '';
        return;
    }

    const isValid = isValidAzureUrl(url);
    videoUrlInput.style.borderColor = isValid ? '#2ecc71' : '#e74c3c';
}

// Перевірка формату Azure URL
function isValidAzureUrl(url) {
    try {
        const urlObj = new URL(url);
        // Перевіряємо чи це Azure blob URL
        return urlObj.hostname.includes('.blob.core.windows.net') &&
               urlObj.pathname.length > 1;
    } catch {
        return false;
    }
}

// Обробка натискання кнопки "Зареєструвати"
function handleUpload() {
    const url = videoUrlInput.value.trim();
    const where = metadataWhereInput.value.trim();
    const when = metadataWhenInput.value.trim();

    // Валідація обов'язкових полів
    if (!url) {
        showError('Будь ласка, вкажіть Azure Blob URL відео');
        return;
    }

    if (!isValidAzureUrl(url)) {
        showError('Некоректний Azure Blob URL. Використовуйте формат: https://account.blob.core.windows.net/container/path/file.mp4');
        return;
    }

    // Валідація опційних полів
    if (where && !/^[A-Za-z\s\-_]+$/.test(where)) {
        showError('Локація може містити тільки англійські літери, пробіли, дефіси та підкреслення');
        return;
    }

    if (when && !/^\d{8}$/.test(when)) {
        showError('Дата повинна бути у форматі РРРРММДД (8 цифр)');
        return;
    }

    // Показуємо індикатор завантаження
    showLoading(url);

    // Відправляємо запит на сервер
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
            resetForm();
        }
    })
    .catch(error => {
        console.error('Помилка:', error);
        showError(`Помилка з'єднання з сервером: ${error.message}`);
    });
}

// Обробка відповіді від сервера
function handleUploadResponse(data) {
    if (data.success) {
        showSuccess({
            message: data.message || `Відео ${data.filename} успішно зареєстровано`,
            azure_link: data.azure_link,
            filename: data.filename,
            id: data.id
        });
    } else {
        showError(data.message || 'Невідома помилка при реєстрації відео');
    }
}

// Показати індикатор завантаження
function showLoading(url) {
    resultDiv.innerHTML = `
        <div class="info-message">
            <h3>Перевірка доступності відео...</h3>
            <p>Перевіряємо доступність відео в Azure Storage:</p>
            <p class="url-display">${url}</p>
            <div class="loading-spinner"></div>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Перевіряємо...';
}

// Скидання форми після успішної реєстрації
function resetForm() {
    metadataWhereInput.value = '';
    metadataWhenInput.value = '';
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
    videoUrlInput.style.borderColor = '';
}

// Функція для показу успішного результату
function showSuccess(data) {
    resultDiv.innerHTML = `
        <div class="success-message">
            <h3>Успішно зареєстровано!</h3>
            <p>${data.message}</p>
            <div class="video-info">
                <p><strong>Файл:</strong> ${data.filename}</p>
                <p><strong>ID:</strong> ${data.id}</p>
                <p><strong>Azure посилання:</strong></p>
                <p class="url-display">${data.azure_link}</p>
            </div>
            <div class="action-buttons">
                <a href="/annotator" class="btn btn-primary">Перейти до анотування</a>
                <button class="btn btn-secondary" onclick="clearResult()">Зареєструвати ще одне відео</button>
            </div>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
}

// Функція для показу помилки
function showError(message) {
    resultDiv.innerHTML = `
        <div class="error-message">
            <h3>Помилка реєстрації</h3>
            <p>${message}</p>
            <button class="btn btn-secondary" onclick="clearResult()">Спробувати ще раз</button>
        </div>
    `;
    resultDiv.classList.remove('hidden');
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Зареєструвати відео';
}

// Очистити результат
function clearResult() {
    resultDiv.innerHTML = '';
    resultDiv.classList.add('hidden');
}