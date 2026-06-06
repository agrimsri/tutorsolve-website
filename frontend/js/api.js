/**
 * api.js — Central fetch wrapper for all API calls.
 * Handles JWT token injection, 401 redirect, and JSON parsing.
 */

const _runtimeBackendBase =
  window.__TS_CONFIG__ && window.__TS_CONFIG__.backendBase
    ? String(window.__TS_CONFIG__.backendBase).replace(/\/+$/, "")
    : "";

const API_BASE = _runtimeBackendBase
  ? `${_runtimeBackendBase}/api`
  : window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1"
    ? "http://localhost:5000/api"
    : "https://YOUR_RAILWAY_BACKEND_URL/api";

function normalizeRole(role) {
  const r = (role || "").toString().trim().toLowerCase();
  if (
    r === "superadmin" ||
    r === "super-admin" ||
    r === "super admin" ||
    r === "super_admin"
  ) {
    return "super_admin";
  }
  return r;
}

function parseJwtPayload(token) {
  try {
    const parts = (token || "").split(".");
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(
      base64.length + ((4 - (base64.length % 4)) % 4),
      "=",
    );
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
  if (
    window.location.pathname !== "/" &&
    window.location.pathname !== "/index.html"
  ) {
    window.location.href = "/index.html";
  }
}

async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("ts_token");
  const headers = {
    ...options.headers,
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
    headers,
  };

  const res = await fetch(`${API_BASE}${path}`, fetchOptions);
  if (res.status === 401 && !path.includes("/auth/login")) {
    clearAuth();
    redirectToHome();
    return;
  }

  return res;
}

function getToken() {
  return localStorage.getItem("ts_token");
}
function getRole() {
  return normalizeRole(localStorage.getItem("ts_role"));
}
function getDashboardUrl(role = getRole(), fallback = "/index.html") {
  const dashboardUrls = {
    student: "/student/dashboard.html",
    expert: "/expert/dashboard.html",
    employee: "/admin/dashboard.html",
    super_admin: "/super-admin/dashboard.html",
  };
  return dashboardUrls[normalizeRole(role)] || fallback;
}
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

function getSidebarRoleLabel() {
  const path = window.location.pathname;
  if (path.startsWith("/super-admin/")) return "Super Admin";
  if (path.startsWith("/admin/")) return "Admin";
  if (path.startsWith("/expert/")) return "Expert";
  if (path.startsWith("/student/")) return "Student";
  return "Workspace";
}

function enhanceSidebarBrand() {
  document.querySelectorAll(".sidebar").forEach((sidebar) => {
    if (sidebar.querySelector(".sidebar-brand")) return;

    const existingLogo = Array.from(sidebar.children).find((child) =>
      child.classList && child.classList.contains("sidebar-logo")
    );
    if (!existingLogo) return;

    const roleLabel = getSidebarRoleLabel();
    const brand = document.createElement("div");
    brand.className = "sidebar-brand";
    brand.innerHTML = `
      <a href="/index.html" class="sidebar-back-link" aria-label="Back to TutorSolve landing page">
        <svg class="sidebar-back-icon" width="17" height="17" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M10 12L6 8l4-4"></path>
          <path d="M6.5 8H14"></path>
        </svg>
      </a>
      <a href="/index.html" class="sidebar-logo" aria-label="TutorSolve landing page">
        <img src="/assets/logo.svg" alt="TutorSolve" width="30" height="30">
        <span class="sidebar-brand-copy">
          <span class="navbar-logo-text">TutorSolve</span>
          <span class="sidebar-role-label">${roleLabel}</span>
        </span>
      </a>`;

    existingLogo.replaceWith(brand);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", enhanceSidebarBrand);
} else {
  enhanceSidebarBrand();
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
(function (d, t) {
  var BASE_URL = "https://app.chatwoot.com";
  var g = d.createElement(t),
    s = d.getElementsByTagName(t)[0];
  g.src = BASE_URL + "/packs/js/sdk.js";
  g.async = true;
  s.parentNode.insertBefore(g, s);
  g.onload = function () {
    window.chatwootSDK.run({
      websiteToken: "ocZ6t6gH3mrQyLAYDNV6g38a",
      baseUrl: BASE_URL,
    });
  };
})(document, "script");
