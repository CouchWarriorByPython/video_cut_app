// DOM елементи
const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const videoUrlInput = document.getElementById('video-url');
const metadataWhereInput = document.getElementById('metadata-where');
const metadataWhenInput = document.getElementById('metadata-when');
const uploadBtn = document.getElementById('upload-btn');
const resultDiv = document.getElementById('result');

// Змінна для зберігання файлу
let selectedFile = null;

// Налаштування drag-and-drop
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, highlight, false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, unhighlight, false);
});

function highlight() {
    dropArea.classList.add('highlight');
}

function unhighlight() {
    dropArea.classList.remove('highlight');
}

// Обробники подій
dropArea.addEventListener('drop', handleDrop, false);
dropArea.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileSelect);
uploadBtn.addEventListener('click', handleUpload);

// Після вибору файлу через drag-and-drop
function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;

    if (files.length === 1 && files[0].type.startsWith('video/')) {
        selectedFile = files[0];
        dropArea.innerHTML = `<p>Вибрано: ${selectedFile.name}</p>`;
        videoUrlInput.value = '';  // Очищаємо URL поле
    }
}

// Після вибору файлу через input
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file && file.type.startsWith('video/')) {
        selectedFile = file;
        dropArea.innerHTML = `<p>Вибрано: ${selectedFile.name}</p>`;
        videoUrlInput.value = '';  // Очищаємо URL поле
    }
}

// Обробка натискання кнопки "Завантажити"
function handleUpload() {
    // Отримуємо метадані
    const where = metadataWhereInput.value;
    const when = metadataWhenInput.value;

    // Перевіряємо, який метод завантаження вибрано
    if (selectedFile) {
        // Завантаження через файл
        const formData = new FormData();
        formData.append('video', selectedFile);
        formData.append('where', where || null);
        formData.append('when', when || null);

        uploadFile(formData);
    } else if (videoUrlInput.value.trim()) {
        // Завантаження через Azure URL
        uploadByUrl(videoUrlInput.value.trim(), where, when);
    } else {
        // Немає ні файлу, ні URL
        showError('Будь ласка, виберіть файл або вкажіть URL для завантаження');
    }
}

// Завантаження через файл
function uploadFile(formData) {
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        handleUploadResponse(data);
        resetForm();
    })
    .catch(error => {
        showError('Помилка завантаження файлу');
        console.error('Error:', error);
    });
}

// Завантаження через URL
function uploadByUrl(url, where, when) {
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
    .then(response => response.json())
    .then(data => {
        handleUploadResponse(data);
        resetForm();
    })
    .catch(error => {
        showError('Помилка завантаження з URL');
        console.error('Error:', error);
    });
}

// Обробка відповіді від сервера
function handleUploadResponse(data) {
    if (data.success) {
        showResult({
            success: true,
            message: `Відео ${data.source || data.filename || ""} успішно завантажено`,
            source: data.source
        });
    } else {
        showError(`Помилка: ${data.error || data.message || 'Невідома помилка'}`);
    }
}

// Скидання форми після завантаження
function resetForm() {
    selectedFile = null;
    dropArea.innerHTML = '<p>Перетягніть відео сюди або натисніть для вибору файлу</p>';
    videoUrlInput.value = '';
    metadataWhereInput.value = '';
    metadataWhenInput.value = '';
}

// Функція для показу результату
function showResult(data) {
    if (data.success) {
        resultDiv.innerHTML = `
            <div class="success-message">
                <h3>Успішно!</h3>
                <p>${data.message}</p>
                ${data.source ? `<p>Назва відео: ${data.source}</p>` : ''}
            </div>
        `;
    } else {
        showError(data.message || data.error || 'Помилка при завантаженні відео');
    }
    resultDiv.classList.remove('hidden');
}

// Функція для показу помилки
function showError(message) {
    resultDiv.innerHTML = `
        <div class="error-message">
            <h3>Помилка!</h3>
            <p>${message}</p>
        </div>
    `;
    resultDiv.classList.remove('hidden');
}