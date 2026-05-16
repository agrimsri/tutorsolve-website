/**
 * file-upload.js — Drag-and-drop solution file upload for experts.
 */
function initUpload(questionId) {
    const zone = document.getElementById("upload-zone");
    if (!zone) return;

    zone.addEventListener("dragover", e => {
        e.preventDefault();
        zone.classList.add("drag-over");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
    zone.addEventListener("drop", e => {
        e.preventDefault();
        zone.classList.remove("drag-over");
        const file = e.dataTransfer.files[0];
        if (file) uploadFile(questionId, file);
    });

    const input = document.getElementById("file-input");
    if (input) {
        input.addEventListener("change", () => {
            if (input.files[0]) uploadFile(questionId, input.files[0]);
        });
    }
}

async function uploadFile(questionId, file) {
    const bar = document.getElementById("upload-progress");
    const formData = new FormData();
    formData.append("file", file);

    if (bar) bar.style.width = "30%";

    const res = await apiFetch(`/files/upload/${questionId}`, { method: "POST", body: formData });
    const data = await res.json();

    if (bar) bar.style.width = "100%";
    if (!res.ok) {
        toast("Upload failed: " + (data.error || "Unknown error"), "error");
        return;
    }
    toast("Solution uploaded successfully!");
}
