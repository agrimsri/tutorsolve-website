/**
 * modal.js
 * Provides generic, reusable confirmation modals dynamically attached to the DOM.
 */

window.showConfirmModal = function ({ title = "Confirm Action", message = "Are you sure?", confirmText = "Confirm", cancelText = "Cancel", isDanger = false } = {}) {
    return new Promise((resolve) => {
        // Create backdrop
        const overlay = document.createElement("div");
        overlay.className = "modal active";

        // Modal container
        const modalContent = document.createElement("div");
        modalContent.className = "modal-content";
        modalContent.style.maxWidth = "400px";

        // Header
        const header = document.createElement("div");
        header.style.display = "flex";
        header.style.justifyContent = "space-between";
        header.style.alignItems = "center";
        header.style.marginBottom = "var(--space-4)";

        const titleEl = document.createElement("h2");
        titleEl.textContent = title;
        titleEl.style.fontSize = "18px";
        titleEl.style.margin = "0";

        const closeBtn = document.createElement("button");
        closeBtn.className = "btn btn-ghost btn-sm";
        closeBtn.textContent = "✕";
        closeBtn.onclick = () => finish(false);

        header.appendChild(titleEl);
        header.appendChild(closeBtn);

        // Body
        const bodyEl = document.createElement("p");
        bodyEl.textContent = message;
        bodyEl.style.color = "var(--color-gray-700)";
        bodyEl.style.marginBottom = "var(--space-6)";
        bodyEl.style.lineHeight = "1.5";
        bodyEl.style.fontSize = "14px";

        // Footer actions
        const footer = document.createElement("div");
        footer.style.display = "flex";
        footer.style.justifyContent = "flex-end";
        footer.style.gap = "var(--space-3)";

        const cancelBtnEl = document.createElement("button");
        cancelBtnEl.className = "btn btn-secondary";
        cancelBtnEl.textContent = cancelText;
        cancelBtnEl.onclick = () => finish(false);

        const confirmBtnEl = document.createElement("button");
        confirmBtnEl.className = `btn ${isDanger ? 'btn-danger' : 'btn-primary'}`;
        confirmBtnEl.textContent = confirmText;
        confirmBtnEl.onclick = () => finish(true);

        footer.appendChild(cancelBtnEl);
        footer.appendChild(confirmBtnEl);

        // Assemble
        modalContent.appendChild(header);
        modalContent.appendChild(bodyEl);
        modalContent.appendChild(footer);
        overlay.appendChild(modalContent);
        document.body.appendChild(overlay);

        // Close on clicking outside
        overlay.addEventListener("mousedown", (e) => {
            if (e.target === overlay) {
                finish(false);
            }
        });

        // Handle ESC key
        const escListener = (e) => {
            if (e.key === "Escape") finish(false);
        };
        document.addEventListener("keydown", escListener);

        function finish(result) {
            document.removeEventListener("keydown", escListener);
            if (document.body.contains(overlay)) {
                overlay.remove();
            }
            resolve(result);
        }
    });
};
