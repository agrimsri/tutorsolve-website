/**
 * api.js — Central fetch wrapper for all API calls.
 * Handles JWT token injection, 401 redirect, and JSON parsing.
 */

const _runtimeBackendBase =
    (window.__TS_CONFIG__ && window.__TS_CONFIG__.backendBase)
    ? String(window.__TS_CONFIG__.backendBase).replace(/\/+$/, "")
    : "";

const API_BASE = _runtimeBackendBase
    ? `${_runtimeBackendBase}/api`
    : (
        (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
            ? "http://localhost:5000/api"
            : "https://YOUR_RAILWAY_BACKEND_URL/api"
    );

function normalizeRole(role) {
    const r = (role || "").toString().trim().toLowerCase();
    if (r === "superadmin" || r === "super-admin" || r === "super admin" || r === "super_admin") {
        return "super_admin";
    }
    return r;
}

function parseJwtPayload(token) {
    try {
        const parts = (token || "").split(".");
        if (parts.length !== 3) return null;
        const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
        const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
        return JSON.parse(atob(padded));
    } catch {
        return null;
    }
}

function isTokenExpired(token) {
    const payload = parseJwtPayload(token);
    if (!payload || typeof payload.exp !== "number") return true;
    return payload.exp * 1000 <= Date.now();
}

function redirectToHome() {
    if (window.location.pathname !== "/" && window.location.pathname !== "/index.html") {
        window.location.href = "/index.html";
    }
}

async function apiFetch(path, options = {}) {
    const token = localStorage.getItem("ts_token");
    const headers = {
        ...options.headers
    };

    if (token && isTokenExpired(token)) {
        clearAuth();
        redirectToHome();
        return;
    }

    // Only set Content-Type for JSON bodies
    if (options.body && !(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const fetchOptions = {
        ...options,
        headers
    };

    const res = await fetch(`${API_BASE}${path}`, fetchOptions);
    if (res.status === 401 && !path.includes("/auth/login")) {
        clearAuth();
        redirectToHome();
        return;
    }

    return res;
}

function getToken() { return localStorage.getItem("ts_token"); }
function getRole() { return normalizeRole(localStorage.getItem("ts_role")); }
function isLoggedIn() {
    const token = getToken();
    if (!token || isTokenExpired(token)) {
        clearAuth();
        return false;
    }
    return true;
}

function saveAuth(token, role) {
    localStorage.setItem("ts_token", token);
    localStorage.setItem("ts_role", normalizeRole(role));
}

function clearAuth() {
    localStorage.removeItem("ts_token");
    localStorage.removeItem("ts_role");
}

function requireRole(expectedRole) {
    if (!isLoggedIn()) {
        redirectToHome();
        return false;
    }
    const role = getRole();
    if (role !== normalizeRole(expectedRole)) {
        clearAuth();
        redirectToHome();
        return false;
    }
    return true;
}

// Initialize Chatwoot SDK globally
(function(d,t) {
    var BASE_URL="https://app.chatwoot.com";
    var g=d.createElement(t),s=d.getElementsByTagName(t)[0];
    g.src=BASE_URL+"/packs/js/sdk.js";
    g.async = true;
    s.parentNode.insertBefore(g,s);
    g.onload=function(){
      window.chatwootSDK.run({
        websiteToken: 'EnrgswkA2MhhyTPpNxEU48t5',
        baseUrl: BASE_URL
      })
    }
})(document,"script");
