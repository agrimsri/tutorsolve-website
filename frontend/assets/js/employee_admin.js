// ===============================
// INTERESTED QUESTIONS (Default)
// ===============================

async function showInterestedQuestions() {
  const container = document.getElementById("employeeContent");

  container.innerHTML = `
    <div class="card">
      <h3>Questions With Interested Experts</h3>

      <table id="interestedTable">
        <thead>
          <tr>
            <th>Title</th>
            <th>Department</th>
            <th>Student</th>
            <th># Interested</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colspan="5" class="empty">Loading...</td>
          </tr>
        </tbody>
      </table>
    </div>
  `;

  loadInterestedQuestions();
}

async function loadInterestedQuestions() {
  const res = await apiRequest("/employee-admin/questions/interested");

  const tbody = document.querySelector("#interestedTable tbody");
  tbody.innerHTML = "";

  if (!res.ok) {
    tbody.innerHTML = "<tr><td colspan='5'>Error loading data</td></tr>";
    return;
  }

  if (res.data.questions.length === 0) {
    tbody.innerHTML = "<tr><td colspan='5'>No interested questions</td></tr>";
    return;
  }

  res.data.questions.forEach((q) => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${q.title}</td>
      <td>${q.department}</td>
      <td>${q.student_name}</td>
      <td>${q.interested_count}</td>
      <td>
        <button onclick="viewInterestedExperts('${q.question_id}')">
          View
        </button>
      </td>
    `;

    tbody.appendChild(row);
  });
}

async function viewInterestedExperts(questionId) {
  const container = document.getElementById("employeeContent");

  container.innerHTML = `
    <div class="card">
      <h3>Loading question details...</h3>
    </div>
  `;

  const res = await apiRequest(
    `/employee-admin/questions/detail/${questionId}`,
  );

  if (!res.ok) {
    container.innerHTML = `
      <div class="card">
        <p>Error loading details</p>
      </div>
    `;
    return;
  }

  const q = res.data;

  container.innerHTML = `
    <div class="card">
      <h3>${q.title}</h3>
      <p><strong>Department:</strong> ${q.department}</p>
      <p><strong>Student:</strong> ${q.student_name}</p>
      <p>${q.description}</p>
    </div>

    <div class="card">
      <h3>Interested Experts</h3>

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Department</th>
            <th>Select</th>
          </tr>
        </thead>
        <tbody id="expertListBody"></tbody>
      </table>
    </div>

    <button onclick="showInterestedQuestions()">← Back</button>
  `;

  const tbody = document.getElementById("expertListBody");

  if (q.interested_experts.length === 0) {
    tbody.innerHTML = "<tr><td colspan='4'>No interested experts</td></tr>";
    return;
  }

  q.interested_experts.forEach((exp) => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${exp.name}</td>
      <td>${exp.email}</td>
      <td>${exp.department}</td>
      <td>
        <button onclick="selectExpert('${q.question_id}', '${exp.expert_id}')">
          Select
        </button>
      </td>
    `;

    tbody.appendChild(row);
  });
}

// ===============================
// ACTIVE ORDERS
// ===============================

function showActiveOrders() {
  const container = document.getElementById("employeeContent");

  container.innerHTML = `
    <div class="card">
      <h3>Active Orders</h3>
      <p class="empty">No active orders yet.</p>
    </div>
  `;
}

// ===============================
// PRICING PENDING
// ===============================

function showPricingPending() {
  const container = document.getElementById("employeeContent");

  container.innerHTML = `
    <div class="card">
      <h3>Pricing Pending Super Admin Approval</h3>
      <p class="empty">No pricing requests pending.</p>
    </div>
  `;
}

// ===============================
// COMPLETED ORDERS
// ===============================

function showCompletedOrders() {
  const container = document.getElementById("employeeContent");

  container.innerHTML = `
    <div class="card">
      <h3>Completed Orders</h3>
      <p class="empty">No completed orders yet.</p>
    </div>
  `;
}

// ===============================
// LOGOUT
// ===============================

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.location.href = "/";
}
