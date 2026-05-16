/**
 * admin-cockpit.js — Split-view cockpit logic.
 * Left panel = Student chat (Thread A). Right panel = Expert chat (Thread B).
 */
let threadAId = null;
let threadBId = null;

function initCockpit(tA, tB) {
    threadAId = tA;
    threadBId = tB;
    if (tA) { loadMessages(tA); startPolling(tA); }
    if (tB) { loadMessages(tB); startPolling(tB); }
}

async function forwardFile(fileId) {
    const res = await apiFetch(`/files/${fileId}/unlock`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
        toast("File forwarded to student.");
    } else {
        toast("Error: " + (data.error || "Forward failed"), "error");
    }
}

async function assignExpert(questionId, expertId) {
    const res = await apiFetch(`/admin/orders/${questionId}/assign`, {
        method: "POST",
        body: JSON.stringify({ expert_id: expertId })
    });
    const data = await res.json();
    return res.ok ? data : null;
}
