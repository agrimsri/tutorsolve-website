/**
 * trust-signals.js — Polls /api/trust-signals every 10 seconds.
 * Include on the landing page.
 */
let tickerItems  = [];
let tickerIndex  = 0;

async function updateTrustSignals() {
    try {
        const res  = await fetch(`${API_BASE}/trust-signals`);
        const data = await res.json();

        const el1 = document.getElementById("active-experts");
        const el2 = document.getElementById("questions-solved");
        if (el1) el1.textContent = data.active_experts.toLocaleString();
        if (el2) el2.textContent = data.questions_solved.toLocaleString();

        if (data.ticker && data.ticker.length > 0) {
            tickerItems = data.ticker;
        }
    } catch { /* fail silently */ }
}

function rotateTicker() {
    const el = document.getElementById("ticker-feed");
    if (!el || tickerItems.length === 0) return;
    el.style.opacity = "0";
    setTimeout(() => {
        el.textContent = tickerItems[tickerIndex % tickerItems.length];
        el.style.opacity = "1";
        tickerIndex++;
    }, 300);
}

updateTrustSignals();
setInterval(updateTrustSignals, 10000);
setInterval(rotateTicker, 5000);
