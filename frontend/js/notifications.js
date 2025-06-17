const Notifications = {
    /**
     * Показати інформаційне повідомлення
     */
    async show(message, type = 'info', title = null) {
        return new Promise((resolve) => {
            const modal = this._createModal(message, type, title, 'notification');

            modal.addEventListener('click', (e) => {
                if (e.target.dataset.action === 'ok' || e.target === modal) {
                    modal.remove();
                    resolve();
                }
            });

            this._showModal(modal);
        });
    },

    /**
     * Показати підтвердження
     */
    async confirm(message, title = 'Підтвердження') {
        return new Promise((resolve) => {
            const modal = this._createModal(message, 'warning', title, 'confirm');

            modal.addEventListener('click', (e) => {
                if (e.target.dataset.action === 'confirm') {
                    modal.remove();
                    resolve(true);
                } else if (e.target.dataset.action === 'cancel' || e.target === modal) {
                    modal.remove();
                    resolve(false);
                }
            });

            this._showModal(modal);
        });
    },

    /**
     * Створити модальне вікно
     */
    _createModal(message, type, title, modalType) {
        const modal = document.createElement('div');
        modal.className = `notification-modal ${type}`;

        const titles = {
            success: 'Успіх',
            error: 'Помилка',
            warning: 'Увага',
            info: 'Інформація'
        };

        const modalTitle = title || titles[type] || 'Повідомлення';
        const buttons = this._createButtons(modalType);

        modal.innerHTML = `
            <div class="notification-modal-content">
                <h3>${Utils.escapeHtml(modalTitle)}</h3>
                <p>${Utils.escapeHtml(message)}</p>
                ${buttons}
            </div>
        `;

        return modal;
    },

    /**
     * Створити кнопки залежно від типу модального вікна
     */
    _createButtons(modalType) {
        if (modalType === 'confirm') {
            return `
                <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="btn btn-secondary" data-action="cancel">Скасувати</button>
                    <button class="btn btn-success" data-action="confirm">Підтвердити</button>
                </div>
            `;
        }

        return '<button class="btn btn-success" data-action="ok">OK</button>';
    },

    /**
     * Показати модальне вікно
     */
    _showModal(modal) {
        document.body.appendChild(modal);
        modal.style.display = 'block';

        const focusButton = modal.querySelector('[data-action="confirm"], [data-action="ok"]');
        if (focusButton) {
            focusButton.focus();
        }

        this._handleKeyboardEvents(modal);
    },

    /**
     * Обробка клавіатури
     */
    _handleKeyboardEvents(modal) {
        const keyHandler = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', keyHandler);
            }
        };

        document.addEventListener('keydown', keyHandler);
    }
};

/**
 * Глобальні функції для зворотної сумісності
 */
window.showNotification = (message, type, title) => Notifications.show(message, type, title);
window.showConfirm = (message, title) => Notifications.confirm(message, title);
window.Notifications = Notifications;