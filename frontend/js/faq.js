// Дані про типи дронів з масивом фотографій
const droneTypes = {
    'autel': {
        name: 'Autel',
        images: [
            { src: 'autel_1.jpeg' },
            { src: 'autel_2.jpeg' },
        ]
    },
    'dji': {
        name: 'DJI',
        images: [
            { src: 'dji_1.jpeg', modification: 'DJI Fly' },
            { src: 'dji_2.jpeg', modification: 'DJI Pilot' },
            { src: 'dji_3.jpeg', modification: 'DJI Pilot' },
        ]
    },
    'flyeye': {
        name: 'FlyEye',
        images: [
            { src: 'flyeye_1.jpeg' },
            { src: 'flyeye_2.jpeg' },
        ]
    },
    'fpv': {
        name: 'FPV',
        description: 'В цю категорію входять FPV-камікадзе або (рідше) саморобні FPV-бомбери. Note: інколи відео може бути не тільки аналоговим, а і цифровим!',
        images: [
            { src: 'fpv_1.png' },
            { src: 'fpv_2.png' },
        ]
    },
    'furia': {
        name: 'Furia',
        images: [
            { src: 'furia_1.jpeg' },
            { src: 'furia_2.jpeg' }
        ]
    },
    'leleka': {
        name: 'Leleka',
        images: [
            { src: 'leleka_1.jpeg' },
            { src: 'leleka_2.jpeg' }
        ]
    },
    'gor': {
        name: 'Gor',
        images: [
            { src: 'gor.jpeg' },
        ]
    },
    'poseidon': {
        name: 'Poseidon',
        images: [
            { src: 'poseidon.jpeg' },
        ]
    },
    'heidrun': {
        name: 'Heidrun',
        images: [
            { src: 'heidrun.jpeg' },
        ]
    },
    'interceptor': {
        name: 'Interceptor',
        images: [
            { src: 'interceptor_1.png' },
            { src: 'interceptor_2.png' },
        ]
    },
    'other_bomber': {
        name: 'Other Bomber',
        description: 'У дронів можуть бути інші довільні інтерфейси або може взагалі не бути OSD, але видно скид боєприпасу (і це не DJI/Autel).',
        images: [
            { src: 'nemezis.jpeg', modification: 'Nemezis' },
            { src: 'vampire.jpeg', modification: 'Vampire' },
        ]
    },
    'other_recon': {
        name: 'Other Recon',
        description: 'У дронів можуть бути інші довільні інтерфейси.',
        images: [
            { src: 'hermes.jpeg', modification: 'Hermes' },
            { src: 'shark.png', modification: 'Shark' },
        ]
    }
};

function generateDroneImages(images, droneName) {
    let imagesHTML = '<div class="drone-images-gallery">';

    images.forEach((imageData, index) => {
        const hasModification = imageData.modification && imageData.modification.trim();
        const caption = hasModification ? imageData.modification : droneName;

        imagesHTML += `
            <div class="drone-image-item">
                <div class="drone-image" 
                     onclick="openLightbox('/static/images/drones/${imageData.src}', '${caption}')">
                    <img src="/static/images/drones/${imageData.src}" 
                         alt="${caption}" 
                         onerror="this.src='/static/images/drones/placeholder.png'">
                </div>
                ${hasModification ? `<div class="image-caption">${imageData.modification}</div>` : ''}
            </div>
        `;
    });

    imagesHTML += '</div>';
    return imagesHTML;
}

function generateDroneContent(droneKey, droneData) {
    const descriptionHTML = droneData.description ?
        `<div class="drone-description">${droneData.description}</div>` : '';

    return `
        <div class="drone-content">
            ${descriptionHTML}
            ${generateDroneImages(droneData.images, droneData.name)}
        </div>
    `;
}

function generateDroneItem(droneKey, droneData) {
    return `
        <div class="accordion-item" data-drone="${droneKey}">
            <div class="accordion-header">
                <h3>${droneData.name}</h3>
                <span class="accordion-icon">▼</span>
            </div>
            <div class="accordion-content">
                ${generateDroneContent(droneKey, droneData)}
            </div>
        </div>
    `;
}

function generateAllDrones() {
    const accordion = document.getElementById('dronesAccordion');
    let html = '';

    for (const [droneKey, droneData] of Object.entries(droneTypes)) {
        html += generateDroneItem(droneKey, droneData);
    }

    accordion.innerHTML = html;
}

function setupDroneAccordion() {
    const accordionItems = document.querySelectorAll('.accordion-item');

    accordionItems.forEach(item => {
        const header = item.querySelector('.accordion-header');
        const content = item.querySelector('.accordion-content');
        const icon = item.querySelector('.accordion-icon');

        header.addEventListener('click', function() {
            const isActive = item.classList.contains('active');

            // Закриваємо всі інші accordion елементи
            accordionItems.forEach(otherItem => {
                if (otherItem !== item && otherItem.classList.contains('active')) {
                    otherItem.classList.remove('active');
                    otherItem.querySelector('.accordion-content').style.maxHeight = null;
                    otherItem.querySelector('.accordion-icon').textContent = '▼';
                }
            });

            if (isActive) {
                item.classList.remove('active');
                content.style.maxHeight = null;
                icon.textContent = '▼';
            } else {
                item.classList.add('active');
                content.style.maxHeight = content.scrollHeight + 'px';
                icon.textContent = '▲';
            }
        });
    });
}

// Lightbox функціональність
function openLightbox(imageSrc, caption) {
    const lightbox = document.getElementById('imageLightbox');
    const lightboxImage = document.getElementById('lightboxImage');
    const lightboxCaption = document.getElementById('lightboxCaption');

    lightboxImage.src = imageSrc;
    lightboxImage.alt = caption;
    lightboxCaption.textContent = caption;

    lightbox.style.display = 'block';
    document.body.style.overflow = 'hidden'; // Заборонити прокрутку фону
}

function closeLightbox() {
    const lightbox = document.getElementById('imageLightbox');
    lightbox.style.display = 'none';
    document.body.style.overflow = 'auto'; // Відновити прокрутку
}

function setupLightbox() {
    const lightbox = document.getElementById('imageLightbox');
    const closeBtn = document.querySelector('.lightbox-close');

    // Закрити при кліку на хрестик
    closeBtn.addEventListener('click', closeLightbox);

    // Закрити при кліку поза зображенням
    lightbox.addEventListener('click', function(e) {
        if (e.target === lightbox || e.target.classList.contains('lightbox-content')) {
            closeLightbox();
        }
    });

    // Закрити при натисканні Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && lightbox.style.display === 'block') {
            closeLightbox();
        }
    });
}

async function initializeFAQ() {
    // Перевіряємо авторизацію перед ініціалізацією
    await checkAuthAndRedirect();

    // Ініціалізуємо контент тільки якщо користувач авторизований
    if (isAuthenticated()) {
        generateAllDrones();
        setupDroneAccordion();
        setupLightbox();
    }
}

document.addEventListener('DOMContentLoaded', initializeFAQ);