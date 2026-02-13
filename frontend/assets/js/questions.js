/* ==========================================
   QUESTION FEATURE LOGIC
========================================== */

async function createQuestion(payload) {
  return await apiRequest("/questions", "POST", payload);
}

async function fetchMyQuestions() {
  return await apiRequest("/questions/mine", "GET");
}

async function fetchAdminQuestions(status = "CREATED") {
  return await apiRequest(`/admin/questions?status=${status}`, "GET");
}

/* ==========================================
   STUDENT FUNCTIONS
========================================== */

async function submitStudentQuestion() {
  const title = document.getElementById("title").value.trim();
  const department = document.getElementById("department").value.trim();
  const description = document.getElementById("description").value.trim();

  if (!title || !department || !description) {
    alert("Please fill all fields.");
    return;
  }

  const res = await createQuestion({
    title,
    department,
    description,
  });

  if (!res.ok) {
    alert(res.data.error || "Failed to submit question");
    return;
  }

  alert("Question submitted successfully!");

  sessionStorage.removeItem("pending_question");

  document.getElementById("title").value = "";
  document.getElementById("department").value = "";
  document.getElementById("description").value = "";

  loadStudentQuestions();
}

async function loadStudentQuestions() {
  const res = await fetchMyQuestions();

  if (!res.ok) {
    console.error(res.data.error);
    return;
  }

  const list = document.getElementById("myQuestions");
  list.innerHTML = "";

  if (res.data.questions.length === 0) {
    list.innerHTML = "<li>No questions posted yet.</li>";
    return;
  }

  res.data.questions.forEach((q) => {
    const li = document.createElement("li");
    li.innerText = `${q.title} — ${q.status}`;
    list.appendChild(li);
  });
}

/* ==========================================
   ADMIN FUNCTIONS
========================================== */

async function loadAdminQuestions() {
  const res = await fetchAdminQuestions("CREATED");

  if (!res.ok) {
    console.error(res.data.error);
    return;
  }

  const tableBody = document.querySelector("#questionTable tbody");
  tableBody.innerHTML = "";

  res.data.questions.forEach((q) => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${q.title}</td>
      <td>${q.department}</td>
      <td>${q.status}</td>
    `;

    tableBody.appendChild(row);
  });
}

/* ==========================================
   LANDING CARRY FORWARD
========================================== */

function handlePendingQuestionCarryForward() {
  const pending = sessionStorage.getItem("pending_question");
  if (!pending) return;

  document.getElementById("description").value = pending;
}
