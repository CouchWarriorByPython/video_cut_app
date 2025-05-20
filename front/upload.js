// DOM елементи
const videoUrlInput = document.getElementById('video-url');
const metadataWhereInput = document.getElementById('metadata-where');
const metadataWhenInput = document.getElementById('metadata-when');
const uploadBtn = document.getElementById('upload-btn');
const resultDiv = document.getElementById('result');

// Обробники подій
uploadBtn.addEventListener('click', handleUpload);

// Обробка натискання кнопки "Завантажити"
function handleUpload() {
    // Отримуємо метадані
    const url = videoUrlInput.value.trim();
    const where = metadataWhereInput.value;
    const when = metadataWhenInput.value;

    if (!url) {
        showError('Будь ласка, вкажіть URL для завантаження');
        return;
    }

    // Показуємо індикатор завантаження
    resultDiv.innerHTML = `
        <div class="info-message">
            <h3>Завантаження...</h3>
            <p>Будь ласка, зачекайте. Відео завантажується з URL: ${url}</p>
        </div>
    `;
    resultDiv.classList.remove('hidden');

    // Завантаження через URL
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
        showError(`Помилка завантаження: ${error.message}`);
    });
}

// Обробка відповіді від сервера
function handleUploadResponse(data) {
    if (data.success) {
        showResult({
            success: true,
            message: `Відео ${data.filename || data.azure_link} успішно завантажено`,
            source: data.local_url || data.azure_link,
            id: data.id
        });
    } else {
        showError(`Помилка: ${data.error || data.message || 'Невідома помилка'}`);
    }
}

// Скидання форми після завантаження
function resetForm() {
    // Залишаємо URL для зручності повторного завантаження
    // videoUrlInput.value = '';
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
                <p>Джерело: ${data.source}</p>
                <p><a href="/annotator" class="btn btn-primary">Перейти до анотації</a></p>
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

// Додаємо CSS для повідомлення про завантаження
document.head.insertAdjacentHTML('beforeend', `
<style>
.info-message {
    background-color: rgba(52, 152, 219, 0.2);
    border-left: 4px solid #3498db;
    padding: 15px;
    border-radius: 4px;
    margin-top: 20px;
}
</style>
`);