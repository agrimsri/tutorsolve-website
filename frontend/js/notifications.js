function initNotifications() {
    const token = localStorage.getItem("ts_token");
    if (!token) return;

    const API_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? "http://localhost:5000"
        : "https://YOUR_RAILWAY_BACKEND_URL"; // <-- UPDATE THIS TO YOUR RAILWAY BACKEND URL ONCE DEPLOYED

    // Attach new_notification listener to a socket (idempotent via .off first)
    function setupNotifListeners(sock) {
        sock.off("new_notification");
        sock.on("new_notification", (data) => {
            updateUnreadCount(1, true);
            // Use toast.js global if available
            if (typeof toast === "function") {
                toast(`${data.title}: ${data.body}`, "info");
            }
            const list = document.getElementById("notif-list");
            if (list) {
                if (list.innerHTML.includes("No new notifications")) {
                    list.innerHTML = "";
                }
                const el = document.createElement("a");
                el.className = "notif-item unread";
                el.href = data.link || "#";
                el.innerHTML = `
                    <div class="notif-title">${data.title}</div>
                    <div class="notif-body">${data.body}</div>
                    <div class="notif-time">Just now</div>
                `;
                list.prepend(el);
            }
        });
    }

    // 1. WebSocket setup: reuse chat socket if available, else create standalone
    if (typeof io !== "undefined") {
        const hasChatJS = typeof getChatSocket === "function";

        if (hasChatJS) {
            // chat.js is on this page — NEVER create a second socket.
            // Poll until the chat socket is connected.
            const checkInterval = setInterval(() => {
                const sock = getChatSocket();
                if (sock && sock.connected) {
                    clearInterval(checkInterval);
                    console.log("[Notifications] Reusing connected chat socket");
                    setupNotifListeners(sock);
                    // Re-attach on reconnect using a named function (prevents accumulation)
                    const onReconnect = () => setupNotifListeners(sock);
                    sock.off("connect", onReconnect);
                    sock.on("connect", onReconnect);
                } else if (sock && !sock.connected) {
                    clearInterval(checkInterval);
                    sock.once("connect", () => {
                        console.log("[Notifications] Attaching after chat socket connected");
                        setupNotifListeners(sock);
                        const onReconnect = () => setupNotifListeners(sock);
                        sock.off("connect", onReconnect);
                        sock.on("connect", onReconnect);
                    });
                }
                // else: socket not yet created — keep polling
            }, 200);
        } else {
            // No chat.js on this page — create a dedicated notification socket
            const socketUrl = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
                ? "http://localhost:5000"
                : "https://YOUR_RAILWAY_BACKEND_URL"; // <-- UPDATE THIS TO YOUR RAILWAY BACKEND URL ONCE DEPLOYED
            const notifSocket = io(socketUrl, {
                auth: { token: token },
                transports: ["websocket", "polling"],
                reconnection: true
            });
            notifSocket.on("connect", () => {
                console.log("[Notifications] Standalone socket connected");
                setupNotifListeners(notifSocket);
            });
        }
    } else {
        console.warn("[Notifications] Socket.io not found. Falling back to polling only.");
    }

    // 2. REST polling fallback (every 45s)
    async function fetchNotifications() {
        try {
            const res = await fetch(`${API_URL}/api/notifications`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                updateUnreadCount(data.unread_count, false);
                renderDropdown(data.notifications);
            }
        } catch (e) {
            console.error("[Notifications] fetch failed:", e);
        }
    }

    // 3. Inject Bell UI
    const isTaskDetailPage = window.location.pathname.includes("task-detail.html");
    let bellBtn = document.getElementById("notif-bell");
    if (!bellBtn && !isTaskDetailPage) {
        bellBtn = document.createElement("div");
        bellBtn.id = "notif-bell";
        bellBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
            <div id="notif-badge">0</div>
            <div id="notif-dropdown">
              <div id="notif-list"></div>
            </div>
        `;
        document.body.appendChild(bellBtn);
    } else if (bellBtn) {
        if (isTaskDetailPage) {
            bellBtn.style.display = "none";
        } else if (bellBtn.parentElement !== document.body) {
            document.body.appendChild(bellBtn);
        }
    }

    fetchNotifications();
    setInterval(fetchNotifications, 45000);

    function updateUnreadCount(count, isIncrement = false) {
        const badge = document.getElementById("notif-badge");
        if (!badge) return;
        let current = parseInt(badge.innerText || "0");
        let newCount = isIncrement ? current + count : count;
        if (newCount > 0) {
            badge.innerText = newCount;
            badge.style.display = "flex";
        } else {
            badge.style.display = "none";
        }
    }

    function renderDropdown(notifs) {
        const list = document.getElementById("notif-list");
        if (!list) return;
        list.innerHTML = "";
        if (!notifs || notifs.length === 0) {
            list.innerHTML = `<div style="padding:10px;color:#666;text-align:center;font-size:0.9rem;">No new notifications</div>`;
            return;
        }
        notifs.forEach(n => {
            const el = document.createElement("a");
            el.className = `notif-item ${n.is_read ? "" : "unread"}`;
            el.href = n.link || "#";
            el.innerHTML = `
                <div class="notif-title">${n.title}</div>
                <div class="notif-body">${n.body}</div>
                <div class="notif-time">${typeof timeAgo === 'function' ? timeAgo(n.created_at) : new Date(n.created_at.replace(" ", "T") + (n.created_at.endsWith("Z") ? "" : "Z")).toLocaleString()}</div>
            `;
            list.appendChild(el);
        });
    }

    const currentBellBtn = document.getElementById("notif-bell");
    if (currentBellBtn) {
        currentBellBtn.addEventListener("click", () => {
            const dropdown = document.getElementById("notif-dropdown");
            if (dropdown) dropdown.classList.toggle("show");
            fetch(`${API_URL}/api/notifications/read`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` }
            }).then(() => updateUnreadCount(0, false)).catch(() => {});
        });
    }

    document.addEventListener("click", (e) => {
        const dropdown = document.getElementById("notif-dropdown");
        if (
            dropdown &&
            dropdown.classList.contains("show") &&
            currentBellBtn &&
            !currentBellBtn.contains(e.target) &&
            !dropdown.contains(e.target)
        ) {
            dropdown.classList.remove("show");
        }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initNotifications);
} else {
    initNotifications();
}
