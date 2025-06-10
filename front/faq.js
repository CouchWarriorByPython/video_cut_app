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
        const caption = imageData.modification ? imageData.modification : droneName;

        imagesHTML += `
            <div class="drone-image-item">
                <div class="drone-image">
                    <img src="/static/images/drones/${imageData.src}" 
                         alt="${caption}" 
                         onerror="this.src='/static/images/drones/placeholder.png'">
                </div>
                <div class="image-caption ${imageData.modification ? 'modification-caption' : 'main-caption'}">
                    ${caption}
                </div>
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

document.addEventListener('DOMContentLoaded', function() {
    // Генеруємо весь контент
    generateAllDrones();

    // Налаштовуємо обробники подій
    setupDroneAccordion();

    // Відкриваємо перший тип дрона за замовчуванням
    const firstDrone = document.querySelector('.accordion-item');
    if (firstDrone) {
        const firstContent = firstDrone.querySelector('.accordion-content');
        const firstIcon = firstDrone.querySelector('.accordion-icon');

        firstDrone.classList.add('active');
        firstContent.style.maxHeight = firstContent.scrollHeight + 'px';
        firstIcon.textContent = '▲';
    }
});