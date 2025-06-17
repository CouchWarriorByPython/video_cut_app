/**
 * Модуль FAQ з типами дронів
 */

class FAQManager {
    constructor() {
        this.droneTypes = this._initializeDroneTypes();
        this.elements = this._initializeElements();

        this._init();
    }

    _initializeDroneTypes() {
        return {
            'autel': {
                name: 'Autel',
                images: [
                    { src: 'autel_1.jpeg' },
                    { src: 'autel_2.jpeg' }
                ]
            },
            'dji': {
                name: 'DJI',
                images: [
                    { src: 'dji_1.jpeg', modification: 'DJI Fly' },
                    { src: 'dji_2.jpeg', modification: 'DJI Pilot' },
                    { src: 'dji_3.jpeg', modification: 'DJI Pilot' }
                ]
            },
            'flyeye': {
                name: 'FlyEye',
                images: [
                    { src: 'flyeye_1.jpeg' },
                    { src: 'flyeye_2.jpeg' }
                ]
            },
            'fpv': {
                name: 'FPV',
                description: 'В цю категорію входять FPV-камікадзе або (рідше) саморобні FPV-бомбери. Note: інколи відео може бути не тільки аналоговим, а і цифровим!',
                images: [
                    { src: 'fpv_1.png' },
                    { src: 'fpv_2.png' }
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
                    { src: 'gor.jpeg' }
                ]
            },
            'poseidon': {
                name: 'Poseidon',
                images: [
                    { src: 'poseidon.jpeg' }
                ]
            },
            'heidrun': {
                name: 'Heidrun',
                images: [
                    { src: 'heidrun.jpeg' }
                ]
            },
            'interceptor': {
                name: 'Interceptor',
                images: [
                    { src: 'interceptor_1.png' },
                    { src: 'interceptor_2.png' }
                ]
            },
            'other_bomber': {
                name: 'Other Bomber',
                description: 'У дронів можуть бути інші довільні інтерфейси або може взагалі не бути OSD, але видно скид боєприпасу (і це не DJI/Autel).',
                images: [
                    { src: 'nemezis.jpeg', modification: 'Nemezis' },
                    { src: 'vampire.jpeg', modification: 'Vampire' }
                ]
            },
            'other_recon': {
                name: 'Other Recon',
                description: 'У дронів можуть бути інші довільні інтерфейси.',
                images: [
                    { src: 'hermes.jpeg', modification: 'Hermes' },
                    { src: 'shark.png', modification: 'Shark' }
                ]
            }
        };
    }

    _initializeElements() {
        return {
            accordion: document.getElementById('dronesAccordion'),
            lightbox: document.getElementById('imageLightbox'),
            lightboxImage: document.getElementById('lightboxImage'),
            lightboxCaption: document.getElementById('lightboxCaption'),
            lightboxClose: document.querySelector('.lightbox-close')
        };
    }

    async _init() {
        await Auth.checkAuthAndRedirect();

        if (Auth.isAuthenticated()) {
            this._generateAllDrones();
            this._setupDroneAccordion();
            this._setupLightbox();
        }
    }

    _generateAllDrones() {
        let html = '';

        for (const [droneKey, droneData] of Object.entries(this.droneTypes)) {
            html += this._generateDroneItem(droneKey, droneData);
        }

        this.elements.accordion.innerHTML = html;
    }

    _generateDroneItem(droneKey, droneData) {
        return `
            <div class="accordion-item" data-drone="${droneKey}">
                <div class="accordion-header">
                    <h3>${Utils.escapeHtml(droneData.name)}</h3>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    ${this._generateDroneContent(droneKey, droneData)}
                </div>
            </div>
        `;
    }

    _generateDroneContent(droneKey, droneData) {
        const descriptionHTML = droneData.description ?
            `<div class="drone-description">${Utils.escapeHtml(droneData.description)}</div>` : '';

        return `
            <div class="drone-content">
                ${descriptionHTML}
                ${this._generateDroneImages(droneData.images, droneData.name)}
            </div>
        `;
    }

    _generateDroneImages(images, droneName) {
        let imagesHTML = '<div class="drone-images-gallery">';

        images.forEach((imageData) => {
            const hasModification = imageData.modification && imageData.modification.trim();
            const caption = hasModification ? imageData.modification : droneName;

            imagesHTML += `
                <div class="drone-image-item">
                    <div class="drone-image"
                         onclick="faqManager.openLightbox('/static/images/drones/${imageData.src}', '${Utils.escapeHtml(caption)}')">
                        <img src="/static/images/drones/${imageData.src}"
                             alt="${Utils.escapeHtml(caption)}"
                             onerror="this.src='/static/images/drones/placeholder.png'">
                    </div>
                    ${hasModification ? `<div class="image-caption">${Utils.escapeHtml(imageData.modification)}</div>` : ''}
                </div>
            `;
        });

        imagesHTML += '</div>';
        return imagesHTML;
    }

    _setupDroneAccordion() {
        const accordionItems = document.querySelectorAll('.accordion-item');

        accordionItems.forEach(item => {
            const header = item.querySelector('.accordion-header');
            const content = item.querySelector('.accordion-content');
            const icon = item.querySelector('.accordion-icon');

            header.addEventListener('click', () => {
                const isActive = item.classList.contains('active');

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

    openLightbox(imageSrc, caption) {
        this.elements.lightboxImage.src = imageSrc;
        this.elements.lightboxImage.alt = caption;
        this.elements.lightboxCaption.textContent = caption;

        this.elements.lightbox.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    _closeLightbox() {
        this.elements.lightbox.style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    _setupLightbox() {
        this.elements.lightboxClose.addEventListener('click', () => this._closeLightbox());

        this.elements.lightbox.addEventListener('click', (e) => {
            if (e.target === this.elements.lightbox || e.target.classList.contains('lightbox-content')) {
                this._closeLightbox();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.elements.lightbox.style.display === 'block') {
                this._closeLightbox();
            }
        });
    }
}

/**
 * Ініціалізація при завантаженні сторінки
 */
document.addEventListener('DOMContentLoaded', () => {
    window.faqManager = new FAQManager();
});