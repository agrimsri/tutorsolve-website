/**
 * auth.js — Login, signup, logout, geo-check, password reset.
 */

function hasPendingQuestionDraft() {
    return Boolean(
        localStorage.getItem("ts_pending_order_draft_v1")
        || sessionStorage.getItem("pending_question")
    );
}

function getPendingLandingQuestion() {
    return (sessionStorage.getItem("pending_question") || "").trim();
}

function getStudentOrderDetailUrl(questionId) {
    return `/student/order-detail.html?id=${encodeURIComponent(questionId)}`;
}

function getStudentAskQuestionUrl() {
    return "/student/orders.html?open_post_modal=1";
}

function rememberStudentOrder(questionId) {
    if (!questionId) return;
    sessionStorage.setItem("last_order_id", questionId);
    localStorage.setItem("ts_last_student_order_id", questionId);
}

async function createStudentOrderFromLandingQuestion(questionText) {
    const title = (questionText || "").trim();
    if (!title) return null;

    const res = await apiFetch("/student/orders", {
        method: "POST",
        body: JSON.stringify({ title, domain: "Other" }),
    });
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.error || "Failed to create order");
    }

    const questionId = data.question_id || data._id || data.id;
    if (!questionId) {
        throw new Error("Created order is missing an id");
    }

    sessionStorage.removeItem("pending_question");
    rememberStudentOrder(questionId);
    return getStudentOrderDetailUrl(questionId);
}

async function getLatestStudentOrderDetailUrl(fallback = "/student/dashboard.html") {
    try {
        const res = await apiFetch("/student/orders");
        if (!res || !res.ok) throw new Error("Could not load orders");

        const orders = await res.json();
        if (Array.isArray(orders) && orders.length > 0) {
            const latestOrder = orders[0];
            const questionId = latestOrder._id || latestOrder.id || latestOrder.question_id;
            if (questionId) {
                rememberStudentOrder(questionId);
                return getStudentOrderDetailUrl(questionId);
            }
        }
    } catch (_err) {
        const rememberedOrderId = localStorage.getItem("ts_last_student_order_id");
        if (rememberedOrderId) {
            return getStudentOrderDetailUrl(rememberedOrderId);
        }
    }

    return fallback;
}

async function getStudentPostAuthRedirectUrl() {
    const pendingLandingQuestion = getPendingLandingQuestion();
    if (pendingLandingQuestion) {
        try {
            return await createStudentOrderFromLandingQuestion(pendingLandingQuestion);
        } catch (err) {
            if (typeof toast === "function") {
                toast(err.message || "Could not create your pending question.", "error");
            }
            return "/student/orders.html";
        }
    }

    if (
        (window.PendingQuestionDraft && window.PendingQuestionDraft.hasDraft())
        || localStorage.getItem("ts_pending_order_draft_v1")
    ) {
        return "/student/orders.html";
    }

    return getLatestStudentOrderDetailUrl();
}

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

    window.location.href = normalizeRole(data.role) === "student"
        ? await getStudentPostAuthRedirectUrl()
        : getDashboardUrl(data.role, "/auth/login.html");
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

    // After signup, submit a landing question if present, else continue to saved draft/latest order.
    const redirectUrl = await getStudentPostAuthRedirectUrl();
    window.location.href = redirectUrl;
}

async function expertApply(formData) {
    // formData is a FormData object (for file uploads)
    const res = await apiFetch("/auth/expert-apply", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Application failed");
    return data;
}

async function forgotPassword(email) {
    const res = await apiFetch("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to request password reset");
    return data;
}

async function resetPassword(email, token, new_password, confirm_password) {
    const res = await apiFetch("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ email, token, new_password, confirm_password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to reset password");
    return data;
}

function logout() {
    clearAuth();
    window.location.href = "/index.html";
}

function redirectStudentAskQuestionAccess() {
    if (!isLoggedIn() || getRole() !== "student") return false;
    window.location.href = getStudentAskQuestionUrl();
    return true;
}

function wireStudentAskQuestionLinks() {
    const shouldRouteStudent =
        typeof isLoggedIn === "function" && isLoggedIn() && getRole() === "student";

    if (
        shouldRouteStudent &&
        window.location.pathname === "/pages/ask-question.html"
    ) {
        redirectStudentAskQuestionAccess();
        return;
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest('a[href="/pages/ask-question.html"]');
        if (!link) return;
        if (!isLoggedIn() || getRole() !== "student") return;

        event.preventDefault();
        window.location.href = getStudentAskQuestionUrl();
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireStudentAskQuestionLinks);
} else {
    wireStudentAskQuestionLinks();
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
