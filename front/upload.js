// DOM елементи
const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const uploadForm = document.getElementById('video-upload-form');
const resultDiv = document.getElementById('result');

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

// Обробка форми завантаження з Azure
uploadForm.addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const videoUrl = document.getElementById('video-url').value;
    const where = document.getElementById('where').value;
    const when = document.getElementById('when').value;

    fetch('/upload_from_azure', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            video_url: videoUrl,
            where: where || null,
            when: when || null
        }),
    })
    .then(response => response.json())
    .then(data => {
        showResult(data);
    })
    .catch(error => {
        showError('Сталася помилка під час обробки запиту.');
        console.error('Error:', error);
    });
});

// Функція обробки drag-and-drop
function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;

    if (files.length === 1 && files[0].type.startsWith('video/')) {
        handleVideoFile(files[0]);
    }
}

// Функція вибору файлу через input
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file && file.type.startsWith('video/')) {
        handleVideoFile(file);
    }
}

// Обробка відео файлу
function handleVideoFile(file) {
    const formData = new FormData();
    formData.append('video', file);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showResult({
                success: true,
                message: `Відео ${data.filename} успішно завантажено`,
                source: data.source
            });
        } else {
            showError(`Помилка: ${data.error}`);
        }
    })
    .catch(error => {
        showError('Помилка завантаження відео');
        console.error('Error:', error);
    });
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
        showError(data.message || 'Помилка при завантаженні відео');
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