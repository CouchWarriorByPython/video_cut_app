class FAQManager {
    constructor() {
        this.elements = {
            lightbox: document.getElementById('imageLightbox'),
            lightboxImage: document.getElementById('lightboxImage'),
            lightboxCaption: document.getElementById('lightboxCaption'),
            lightboxClose: document.querySelector('.lightbox-close')
        };
        this._init();
    }

    async _init() {
        if (!await auth.checkAccess()) return;
        this._setupAccordion();
        this._setupLightbox();
    }

    _setupAccordion() {
        document.addEventListener('click', e => {
            const header = e.target.closest('.accordion-header');
            if (!header) return;

            const item = header.closest('.accordion-item');
            const content = item.querySelector('.accordion-content');
            const icon = item.querySelector('.accordion-icon');
            const isActive = item.classList.contains('active');

            document.querySelectorAll('.accordion-item.active').forEach(activeItem => {
                if (activeItem !== item) {
                    activeItem.classList.remove('active');
                    activeItem.querySelector('.accordion-content').style.maxHeight = null;
                    activeItem.querySelector('.accordion-icon').textContent = '▼';
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
    }

    openLightbox(imageSrc, caption) {
        Object.assign(this.elements.lightboxImage, { src: imageSrc, alt: caption });
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

        this.elements.lightbox.addEventListener('click', e => {
            if (e.target === this.elements.lightbox || e.target.classList.contains('lightbox-content')) {
                this._closeLightbox();
            }
        });

        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && this.elements.lightbox.style.display === 'block') {
                this._closeLightbox();
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.faqManager = new FAQManager();
});