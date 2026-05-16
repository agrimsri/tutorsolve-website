/**
 * auth.js — Login, signup, logout, geo-check.
 */

async function login(email, password) {
    const res = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
    });
    const data = await res.json();

    if (res.status === 403 && data.error === "BLOCKED_REGION") {
        if (typeof toast === "function") {
            toast("Access from your region is not permitted.", "error");
        }
        setTimeout(() => { window.location.href = "/"; }, 2000);
        return;
    }

    if (!res.ok) throw new Error(data.error || "Login failed");

    saveAuth(data.token, data.role);

    const studentRedirectUrl = sessionStorage.getItem("pending_question") ? "/student/orders.html" : "/student/dashboard.html";

    const roleRedirects = {
        student: studentRedirectUrl,
        expert: "/expert/dashboard.html",
        employee: "/admin/dashboard.html",
        super_admin: "/super-admin/dashboard.html",
    };
    window.location.href = roleRedirects[data.role] || "/auth/login.html";
}

async function signup(formData) {
    const res = await apiFetch("/auth/signup", {
        method: "POST",
        body: JSON.stringify(formData)
    });
    const data = await res.json();

    if (res.status === 403 && data.error === "BLOCKED_REGION") {
        // Show a helpful message before redirecting
        if (typeof toast === "function") {
            toast("Student signups aren't available in your region. You can apply as an expert", "info");
        }
        setTimeout(() => {
            window.location.href = "/";
        }, 2000);
        return;
    }
    if (!res.ok) throw new Error(data.error || "Signup failed");

    saveAuth(data.token, data.role);

    // After signup, redirect to student orders if there's a pending question, else dashboard
    const redirectUrl = sessionStorage.getItem("pending_question") ? "/student/orders.html" : "/student/dashboard.html";
    window.location.href = redirectUrl;
}

async function expertApply(formData) {
    // formData is a FormData object (for file uploads)
    const res = await apiFetch("/auth/expert-apply", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Application failed");
    return data;
}

function logout() {
    clearAuth();
    window.location.href = "/index.html";
}

async function geoCheck() {
    try {
        const res = await fetch(`${API_BASE}/auth/geo-check`);
        const data = await res.json();
        return data.blocked;
    } catch {
        return false;  // Fail open
    }
}
