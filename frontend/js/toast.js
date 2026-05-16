/**
 * toast.js — Flexible toast notification system.
 * Usage: toast(message, type)
 * Types: "success" | "error" | "warning" | "info"
 * Default type: "success"
 */

function toast(message, type = "success", duration = 3500) {
    const container = getOrCreateContainer();

    const el = document.createElement("div");
    el.className = `toast toast--${type}`;

    // Icon per type
    const icons = {
        success: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>
                <path d="M5 8l2 2 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>`,
        error: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>
                <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>`,
        warning: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 2L14 13H2L8 2z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
                <path d="M8 6v3M8 11v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>`,
        info: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>
                <path d="M8 7v4M8 5v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>`,
    };

    el.innerHTML = `
    <span class="toast__icon">${icons[type] || icons.info}</span>
    <span class="toast__message">${message}</span>
    <button class="toast__close" onclick="this.parentElement.remove()">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </button>
  `;

    container.appendChild(el);

    // Trigger enter animation
    requestAnimationFrame(() => el.classList.add("toast--visible"));

    // Auto-dismiss
    setTimeout(() => {
        el.classList.remove("toast--visible");
        el.addEventListener("transitionend", () => el.remove(), { once: true });
    }, duration);
}

function getOrCreateContainer() {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }
    return container;
}
