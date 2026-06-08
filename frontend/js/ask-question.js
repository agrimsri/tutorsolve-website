const askState = {
  files: [],
};

const askEls = {
  title: document.getElementById("ask-title"),
  domain: document.getElementById("ask-domain"),
  description: document.getElementById("ask-description"),
  deadline: document.getElementById("ask-deadline"),
  zone: document.getElementById("ask-upload-zone"),
  fileInput: document.getElementById("ask-file-input"),
  fileList: document.getElementById("ask-file-list"),
  submit: document.getElementById("ask-submit-btn"),
};

function setMinimumDeadline() {
  const today = new Date();
  const iso = today.toISOString().slice(0, 10);
  askEls.deadline.min = iso;
}

async function loadDomains() {
  try {
    const res = await apiFetch("/auth/domains");
    if (!res || !res.ok) throw new Error("Failed to fetch domains");
    const domains = await res.json();
    askEls.domain.innerHTML = '<option value="">Select your domain</option>';
    domains.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.id;
      opt.textContent = d.name;
      askEls.domain.appendChild(opt);
    });
  } catch (_err) {
    askEls.domain.innerHTML =
      '<option value="">Could not load domains</option>';
  }
}

function renderFiles() {
  askEls.fileList.innerHTML = "";
  askState.files.forEach((file, index) => {
    const row = document.createElement("div");
    row.className = "ask-file-row";
    row.innerHTML = `
      <span class="ask-file-name">${escapeHtml(file.name)} (${Math.max(1, Math.round(file.size / 1024))} KB)</span>
      <button type="button" class="ask-file-remove" data-index="${index}" aria-label="Remove file">x</button>
    `;
    askEls.fileList.appendChild(row);
  });
}

function addFiles(fileList) {
  const MAX_MB = 20;
  for (const file of fileList) {
    if (file.size > MAX_MB * 1024 * 1024) {
      toast(`${file.name} is too large. Max ${MAX_MB}MB per file.`, "error");
      continue;
    }
    askState.files.push(file);
  }
  renderFiles();
}

function initFileUpload() {
  if (!askEls.zone || !askEls.fileInput) return;

  askEls.zone.addEventListener("click", () => askEls.fileInput.click());
  askEls.fileInput.addEventListener("change", () =>
    addFiles(askEls.fileInput.files || []),
  );

  askEls.zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    askEls.zone.classList.add("drag-over");
  });

  askEls.zone.addEventListener("dragleave", () => {
    askEls.zone.classList.remove("drag-over");
  });

  askEls.zone.addEventListener("drop", (event) => {
    event.preventDefault();
    askEls.zone.classList.remove("drag-over");
    addFiles(event.dataTransfer.files || []);
  });

  askEls.fileList.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-index]");
    if (!btn) return;
    const index = Number(btn.getAttribute("data-index"));
    if (!Number.isInteger(index)) return;
    askState.files.splice(index, 1);
    renderFiles();
  });
}

function buildPayload() {
  return {
    title: askEls.title.value.trim(),
    domain_id: askEls.domain.value,
    description: askEls.description.value.trim(),
    deadline: askEls.deadline.value || null,
  };
}

async function onSubmit() {
  const payload = buildPayload();
  if (!payload.title) {
    toast("Title is required.", "error");
    askEls.title.focus();
    return;
  }
  if (!payload.domain_id) {
    toast("Domain is required.", "error");
    askEls.domain.focus();
    return;
  }

  askEls.submit.disabled = true;
  const originalLabel = askEls.submit.textContent;
  askEls.submit.textContent = "Saving...";

  try {
    if (isLoggedIn() && getRole() !== "student") {
      toast(
        "Only students can post a question. Please log in with a student account.",
        "error",
      );
      askEls.submit.disabled = false;
      askEls.submit.textContent = originalLabel;
      return;
    }

    if (!window.PendingQuestionDraft) {
      throw new Error("Draft storage is not available.");
    }

    await window.PendingQuestionDraft.saveDraft(payload, askState.files);
    sessionStorage.removeItem("pending_question");

    if (isLoggedIn() && getRole() === "student") {
      toast("Submitting your question from your student account...", "success");
      window.location.href = "/student/orders.html";
      return;
    }

    toast("Question saved. Please log in as a student to continue.", "info");
    window.location.href = "/auth/login.html";
  } catch (err) {
    toast(err.message || "Failed to save your draft.", "error");
    askEls.submit.disabled = false;
    askEls.submit.textContent = originalLabel;
  }
}

function hydrateExistingDraft() {
  if (!window.PendingQuestionDraft) return;
  const draft = window.PendingQuestionDraft.getDraft();
  if (!draft) return;

  askEls.title.value = draft.title || "";
  askEls.domain.value = draft.domain_id || "";
  askEls.description.value = draft.description || "";
  askEls.deadline.value = draft.deadline || "";

  window.PendingQuestionDraft.getFiles()
    .then((files) => {
      askState.files = files.slice();
      renderFiles();
    })
    .catch(() => {
      askState.files = [];
      renderFiles();
    });
}

function enforceStudentOnlyAccess() {
  if (isLoggedIn() && getRole() !== "student") {
    askEls.submit.disabled = true;
    toast(
      "Only students can post a question. Please log in with a student account.",
      "error",
    );
  }
}

async function initAskPage() {
  setMinimumDeadline();
  initFileUpload();
  await loadDomains();
  hydrateExistingDraft();
  enforceStudentOnlyAccess();
  askEls.submit.addEventListener("click", onSubmit);
}

document.addEventListener("DOMContentLoaded", initAskPage);
