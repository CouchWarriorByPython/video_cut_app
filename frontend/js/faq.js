class FAQManager {
    constructor() {
        this.droneTypes = {};
        this.elements = {
            accordion: document.getElementById('dronesAccordion'),
            lightbox: document.getElementById('imageLightbox'),
            lightboxImage: document.getElementById('lightboxImage'),
            lightboxCaption: document.getElementById('lightboxCaption'),
            lightboxClose: document.querySelector('.lightbox-close')
        };

        this._init();
    }

    async _init() {
        if (!await auth.checkAccess()) return;

        await this._loadDroneData();
        this._generateAllDrones();
        this._setupAccordion();
        this._setupLightbox();
    }

    async _loadDroneData() {
        try {
            const response = await fetch('/data/drones.json');
            this.droneTypes = await response.json();
        } catch (error) {
            console.error('Помилка завантаження даних дронів:', error);
            this.droneTypes = this._getFallbackData();
        }
    }

    _getFallbackData() {
        return {
            'dji': {
                name: 'DJI',
                images: [
                    { src: 'dji_1.jpeg', modification: 'DJI Fly' },
                    { src: 'dji_2.jpeg', modification: 'DJI Pilot' }
                ]
            },
            'fpv': {
                name: 'FPV',
                description: 'В цю категорію входять FPV-камікадзе або (рідше) саморобні FPV-бомбери.',
                images: [
                    { src: 'fpv_1.png' },
                    { src: 'fpv_2.png' }
                ]
            }
        };
    }

    _generateAllDrones() {
        const html = Object.entries(this.droneTypes)
            .map(([key, data]) => this._generateDroneItem(key, data))
            .join('');

        this.elements.accordion.innerHTML = html;
    }

    _generateDroneItem(droneKey, droneData) {
        const description = droneData.description ?
            `<div class="drone-description">${utils.escapeHtml(droneData.description)}</div>` : '';

        const images = droneData.images.map(img => {
            const caption = img.modification || droneData.name;
            return `
                <div class="drone-image-item">
                    <div class="drone-image" onclick="faqManager.openLightbox('/static/images/drones/${img.src}', '${utils.escapeHtml(caption)}')">
                        <img src="/static/images/drones/${img.src}" alt="${utils.escapeHtml(caption)}" onerror="this.src='/static/images/drones/placeholder.png'">
                    </div>
                    ${img.modification ? `<div class="image-caption">${utils.escapeHtml(img.modification)}</div>` : ''}
                </div>
            `;
        }).join('');

        return `
            <div class="accordion-item" data-drone="${droneKey}">
                <div class="accordion-header">
                    <h3>${utils.escapeHtml(droneData.name)}</h3>
                    <span class="accordion-icon">▼</span>
                </div>
                <div class="accordion-content">
                    <div class="drone-content">
                        ${description}
                        <div class="drone-images-gallery">${images}</div>
                    </div>
                </div>
            </div>
        `;
    }

    _setupAccordion() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.accordion-header')) {
                const item = e.target.closest('.accordion-item');
                const content = item.querySelector('.accordion-content');
                const icon = item.querySelector('.accordion-icon');
                const isActive = item.classList.contains('active');

                // Закриваємо всі інші
                document.querySelectorAll('.accordion-item.active').forEach(activeItem => {
                    if (activeItem !== item) {
                        activeItem.classList.remove('active');
                        activeItem.querySelector('.accordion-content').style.maxHeight = null;
                        activeItem.querySelector('.accordion-icon').textContent = '▼';
                    }
                });

                // Переключаємо поточний
                if (isActive) {
                    item.classList.remove('active');
                    content.style.maxHeight = null;
                    icon.textContent = '▼';
                } else {
                    item.classList.add('active');
                    content.style.maxHeight = content.scrollHeight + 'px';
                    icon.textContent = '▲';
                }
            }
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

document.addEventListener('DOMContentLoaded', () => {
    window.faqManager = new FAQManager();
});