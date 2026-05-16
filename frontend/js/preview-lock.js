/**
 * preview-lock.js — 25% preview enforcement.
 * Shows unlock modal when student tries to access a locked file.
 */
async function accessFile(fileId, remainingAmount) {
    const res  = await apiFetch(`/files/${fileId}/url`);
    const data = await res.json();

    if (data.locked) {
        showUnlockModal(fileId, remainingAmount);
    } else {
        window.open(data.url, "_blank");
    }
}

function showUnlockModal(fileId, amount) {
    const modal = document.getElementById("unlock-modal");
    if (!modal) return;
    document.getElementById("unlock-amount").textContent = `$${amount}`;
    document.getElementById("unlock-file-id").value = fileId;
    modal.style.display = "flex";
}

function closeUnlockModal() {
    const modal = document.getElementById("unlock-modal");
    if (modal) modal.style.display = "none";
}
