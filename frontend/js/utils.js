/**
 * utils.js — Shared helper functions used across all pages.
 */

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function _ensureUTC(str) {
    if (!str) return str;
    let s = String(str);
    if (!s.endsWith("Z") && !s.includes("+") && !s.includes("T")) {
        s = s.replace(" ", "T") + "Z";
    } else if (!s.endsWith("Z") && !s.includes("+")) {
        s = s + "Z";
    }
    return s;
}

function formatDate(isoString) {
    if (!isoString) return "—";
    return new Date(_ensureUTC(isoString)).toLocaleDateString("en-US", {
        day: "numeric",
        month: "short",
        year: "numeric"
    });
}

function timeAgo(isoString) {
    if (!isoString) return "—";
    const diff = Date.now() - new Date(_ensureUTC(isoString)).getTime();
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
}

const STATUS_CLASSES = {
    awaiting_quote: "awaiting",
    pending_payment: "pending",
    in_progress: "progress",
    reviewing: "reviewing",
    completed: "completed",
    refunded: "refunded",
    cancelled: "awaiting"
};

function statusClass(status) {
    return STATUS_CLASSES[status] || "awaiting";
}

function formatStatus(status) {
    return (status || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Initializes all password visibility toggles on the page.
 * Looks for elements with class .password-toggle inside .password-wrapper.
 */
function initPasswordToggles() {
    document.querySelectorAll(".password-toggle").forEach(btn => {
        // Clear existing listeners by replacing the button if needed (to prevent double-init)
        // btn.onclick = null; 
        
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const wrapper = btn.closest(".password-wrapper");
            const input = wrapper.querySelector("input");
            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            
            // Update icon (Eye vs Eye Off)
            if (isPassword) {
                // Show "Eye Off" icon (crossed out)
                btn.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                        <line x1="1" y1="1" x2="23" y2="23"></line>
                    </svg>`;
            } else {
                // Show "Eye" icon
                btn.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>`;
            }
        });
    });
}

// Auto-init when DOM is ready
document.addEventListener("DOMContentLoaded", initPasswordToggles);

// Global Chart.js defaults
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'bottom',
            labels: {
                font: {
                    family: "'Montserrat', sans-serif",
                    size: 12
                },
                color: '#6B7280'
            }
        },
        tooltip: {
            backgroundColor: '#ffffff',
            titleColor: '#111111',
            bodyColor: '#374151',
            borderColor: '#D1D5DB',
            borderWidth: 1,
            padding: 10,
            bodyFont: {
                family: "'Montserrat', sans-serif",
                size: 12
            },
            titleFont: {
                family: "'Montserrat', sans-serif",
                size: 13,
                weight: 'bold'
            },
            displayColors: true,
            boxPadding: 4
        }
    }
};

const CHART_COLORS = {
    brandPrimary: '#4E4AE5',
    awaiting_quote: '#F59E0B',
    pending_payment: '#F97316',
    in_progress: '#4E4AE5',
    reviewing: '#6366F1',
    completed: '#10B981',
    refunded: '#64748B',
    cancelled: '#64748B',
    domains: ['#3B82F6', '#14B8A6', '#8B5CF6', '#F97316', '#F43F5E', '#84CC16', '#94A3B8']
};
