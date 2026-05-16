/**
 * frontend/js/chat.js
 *
 * Role-separated real-time chat using Socket.IO.
 *
 * Public API:
 *   initStudentChat(threadId, userId, containerId)
 *   initExpertChat(threadId, userId, containerId)
 *   initAdminChat(threadAId, threadBId, userId, containerAId, containerBId)
 *   sendMessage(body, optionalThreadId)
 *   sendAdminMessage(threadId, body)
 *   destroyChat()
 *   getChatSocket()
 */

const SOCKET_URL = API_BASE.replace("/api", "");

let _socket          = null;
let _activeThreadId  = null;   // For student/expert pages
let _currentUserId   = null;
let _onNotification  = null;
let _connectCallback = null;

function getChatSocket() {
    return _socket;
}

function _connect(onConnected) {
    if (_socket && _socket.connected) {
        onConnected(_socket);
        return;
    }

    if (_socket && !_socket.connected) {
        const prev = _connectCallback;
        _connectCallback = (s) => {
            if (prev) prev(s);
            onConnected(s);
        };
        return;
    }

    const token = getToken();
    if (!token) {
        console.warn("[chat] No token found");
        return;
    }

    if (typeof io === "undefined") {
        console.error("[chat] Socket.IO library not loaded");
        return;
    }

    _socket = io(SOCKET_URL, {
        auth: { token },
        transports: ["websocket", "polling"],
        reconnection: true,
        reconnectionDelay: 1500,
        reconnectionAttempts: 10
    });

    _socket.on("connect", () => {
        const indicator = document.getElementById("chat-status");
        if (indicator) indicator.textContent = "";
        
        if (_connectCallback) {
            _connectCallback(_socket);
            _connectCallback = null;
        }
        onConnected(_socket);
    });

    _socket.on("connect_error", (err) => {
        console.error("[chat] Connection error:", err.message);
        const indicator = document.getElementById("chat-status");
        if (indicator) indicator.textContent = "Reconnecting…";
    });

    _socket.on("new_notification", (data) => {
        if (typeof _onNotification === "function") {
            _onNotification(data);
        } else {
            _handleDefaultNotification(data);
        }
    });

    _socket.on("disconnect", () => {
        const indicator = document.getElementById("chat-status");
        if (indicator) indicator.textContent = "Disconnected";
    });

    _socket.on("reconnect", () => {
        const indicator = document.getElementById("chat-status");
        if (indicator) indicator.textContent = "";
        // Socket.IO fires 'connect' on reconnect too, so re-join is handled there.
    });
}

function initStudentChat(threadId, userId, containerId = "chat-messages") {
    _currentUserId = userId;
    _activeThreadId = threadId;

    function joinAndListen(socket) {
        socket.off(`message_history_${threadId}`);
        socket.off("new_message");
        socket.off("error");

        socket.onAny((eventName, ...args) => {
            console.log(`[chat] onAny: received '${eventName}' with args:`, args);
        });

        socket.on(`message_history_${threadId}`, (messages) => {
            console.log(`[chat] Received message_history_${threadId} with ${messages ? messages.length : 0} messages`);
            try {
                _renderHistory(messages, containerId, userId);
            } catch (err) {
                console.error("[chat] Error rendering history:", err);
            }
        });

        socket.on("new_message", (msg) => {
            if (msg.thread_id === threadId) {
                _renderBubble(msg, containerId, userId);
                _scrollBottom(containerId);
            }
        });

        socket.on("error", (err) => {
            console.error("[chat] Server error on join:", err);
            const container = document.getElementById(containerId);
            if (container && container.innerHTML.includes("Fetching chat")) {
                container.innerHTML = `<p style="color:var(--color-gray-400);text-align:center;font-size:14px;margin-top:20px;">
                    Chat unavailable: ${err.message || "Please refresh."}</p>`;
            }
        });

        console.log(`[chat] Emitting join_thread for threadId: ${threadId}`);
        socket.emit("join_thread", { thread_id: threadId, token: getToken() });
    }

    _connect((socket) => {
        joinAndListen(socket);
    });
}

function initExpertChat(threadId, userId, containerId = "chat-messages") {
    _currentUserId = userId;
    _activeThreadId = threadId;

    function joinAndListen(socket) {
        socket.off(`message_history_${threadId}`);
        socket.off("new_message");
        socket.off("error");

        socket.on(`message_history_${threadId}`, (messages) => {
            console.log(`[chat] Received message_history_${threadId} with ${messages ? messages.length : 0} messages`);
            try {
                _renderHistory(messages, containerId, userId);
            } catch (err) {
                console.error("[chat] Error rendering history:", err);
            }
        });

        socket.on("new_message", (msg) => {
            if (msg.thread_id === threadId) {
                _renderBubble(msg, containerId, userId);
                _scrollBottom(containerId);
            }
        });

        socket.on("error", (err) => {
            console.error("[chat] Server error on join:", err);
            const container = document.getElementById(containerId);
            if (container && container.innerHTML.includes("Fetching chat")) {
                container.innerHTML = `<p style="color:var(--color-gray-400);text-align:center;font-size:14px;margin-top:20px;">
                    Chat unavailable: ${err.message || "Please refresh."}</p>`;
            }
        });

        socket.emit("join_thread", { thread_id: threadId, token: getToken() });
    }

    _connect((socket) => {
        joinAndListen(socket);
    });
}

function initAdminChat(threadAId, threadBId, userId, containerAId = "chat-a", containerBId = "chat-b") {
    _currentUserId = userId;

    _connect((socket) => {
        socket.off("new_message");
        if (threadAId) socket.off(`message_history_${threadAId}`);
        if (threadBId) socket.off(`message_history_${threadBId}`);

        if (threadAId) socket.emit("join_thread", { thread_id: threadAId, token: getToken() });
        if (threadBId) socket.emit("join_thread", { thread_id: threadBId, token: getToken() });

        const routeMap = {};
        if (threadAId) routeMap[threadAId] = containerAId;
        if (threadBId) routeMap[threadBId] = containerBId;

        if (threadAId) {
            socket.on(`message_history_${threadAId}`, (messages) => {
                _renderHistory(messages, containerAId, userId);
            });
        }
        if (threadBId) {
            socket.on(`message_history_${threadBId}`, (messages) => {
                _renderHistory(messages, containerBId, userId);
            });
        }

        socket.on("new_message", (msg) => {
            const cid = routeMap[msg.thread_id];
            if (cid) {
                _renderBubble(msg, cid, userId);
                _scrollBottom(cid);
            }
        });
    });
}

function sendMessage(body, threadId = null) {
    const targetId = threadId || _activeThreadId;
    console.log(`[chat] sendMessage called. targetId=${targetId}, body=${body}`);
    if (!_socket) console.error("[chat] sendMessage failed: _socket is null");
    if (!targetId) console.error("[chat] sendMessage failed: targetId is null");
    if (!body.trim()) console.error("[chat] sendMessage failed: body is empty");
    
    if (!_socket || !targetId || !body.trim()) return;
    console.log(`[chat] Emitting send_message to server...`);
    _socket.emit("send_message", {
        thread_id: targetId,
        body: body.trim(),
        token: getToken()
    });
}

function sendAdminMessage(threadId, body) {
    sendMessage(body, threadId);
}

function destroyChat() {
    if (!_socket) return;
    _socket.disconnect();
    _socket = null;
    _activeThreadId = null;
    _connectCallback = null;
}

function _renderHistory(messages, containerId, userId) {
    console.log(`[chat] _renderHistory called for container ${containerId} with messages:`, messages);
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`[chat] _renderHistory: Container ${containerId} not found!`);
        return;
    }
    container.innerHTML = "";
    messages.forEach(msg => _renderBubble(msg, containerId, userId));
    _scrollBottom(containerId);
}

function _renderBubble(msg, containerId, userId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const isMine = msg.sender_user_id === userId;
    const wrap = document.createElement("div");
    wrap.className = `chat-bubble ${isMine ? "chat-bubble--mine" : "chat-bubble--theirs"}`;

    const text = document.createElement("p");
    text.className = "chat-bubble__text";
    text.textContent = msg.body;

    const time = document.createElement("span");
    time.className = "chat-bubble__time";
    time.textContent = _fmtTime(msg.created_at);

    wrap.appendChild(text);
    wrap.appendChild(time);
    container.appendChild(wrap);
}

function _scrollBottom(containerId) {
    const el = document.getElementById(containerId);
    if (el) el.scrollTop = el.scrollHeight;
}

function _fmtTime(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function _handleDefaultNotification(data) {
    const badge = document.getElementById("notif-badge");
    if (badge) {
        const current = parseInt(badge.textContent || "0", 10);
        badge.textContent = current + 1;
        badge.style.display = "inline";
    }
}

function setNotificationHandler(fn) {
    _onNotification = fn;
}