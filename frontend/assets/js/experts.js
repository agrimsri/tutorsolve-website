// ===============================
// EXPERT DASHBOARD DYNAMIC VIEWS
// ===============================

function loadExpertView(view) {
  const container = document.getElementById("expertContent");

  if (!container) return;

  switch (view) {
    case "dashboard":
      container.innerHTML = getExpertDashboardView();
      loadExpertProfile();
      break;

    case "available-questions":
      container.innerHTML = getAvailableQuestionsView();
      loadAvailableQuestions();
      break;

    case "assigned-tasks":
      container.innerHTML = getAssignedTasksView();
      loadAssignedTasks();
      break;

    case "earnings":
      container.innerHTML = getEarningsView();
      loadEarnings();
      break;

    case "profile":
      container.innerHTML = getProfileView();
      loadExpertProfileData();
      break;

    default:
      container.innerHTML = "<p>Page not found</p>";
  }
}

// ----------------------------
// VIEW TEMPLATES
// ----------------------------

function getExpertDashboardView() {
  return `
    <div class="card">
      <h3>Approval Status</h3>
      <div id="approvalStatus" class="status pending">
        Checking approval status...
      </div>
      <p style="margin-top: 10px; font-size: 13px; color: #6b7280">
        Experts can start receiving assignments only after approval.
      </p>
    </div>

    <div id="assignmentSection" style="display: none">
      <div class="card">
        <h3>Available Questions</h3>
        <ul id="availableQuestions" style="list-style: none; padding: 0">
          <li class="empty">Loading questions...</li>
        </ul>
      </div>

      <div class="card">
        <h3>Assigned Tasks</h3>
        <p class="empty">No tasks assigned yet.</p>
      </div>

      <div class="card">
        <h3>Earnings</h3>
        <div class="earnings">₹0.00</div>
        <p style="font-size: 13px; color: #6b7280">
          Earnings are released after task completion and admin verification.
        </p>
      </div>

      <div class="card">
        <h3>Communication Policy</h3>
        <p class="empty">
          All communication is handled by TutorSolve admins. Direct student
          contact is not permitted.
        </p>
      </div>
    </div>
  `;
}

function getAvailableQuestionsView() {
  return `
    <div class="card">
      <h3>Available Questions</h3>
      <ul id="availableQuestions" style="list-style: none; padding: 0">
        <li class="empty">Loading questions...</li>
      </ul>
    </div>
  `;
}

function getAssignedTasksView() {
  return `
    <div class="card">
      <h3>Assigned Tasks</h3>
      <p class="empty">No tasks assigned yet.</p>
    </div>
  `;
}

function getEarningsView() {
  return `
    <div class="card">
      <h3>Earnings</h3>
      <div class="earnings">₹0.00</div>
      <p style="font-size: 13px; color: #6b7280">
        Earnings are released after task completion and admin verification.
      </p>
    </div>
  `;
}

function getProfileView() {
  return `
    <div class="card">
      <h3>Expert Profile</h3>
      <div id="profileContent">
        <p>Loading profile...</p>
      </div>
    </div>
  `;
}

function loadExpertProfileData() {
  const profileContent = document.getElementById("profileContent");
  if (!profileContent) return;

  profileContent.innerHTML = "<p>Loading profile...</p>";

  // Get profile data from /me endpoint
  apiRequest("/me")
    .then((res) => {
      if (!res.ok) {
        profileContent.innerHTML =
          '<p style="color: red;">Failed to load profile</p>';
        return;
      }

      const user = res.data;
      profileContent.innerHTML = `
      <div class="profile-section">
        <div class="profile-header">
          <div class="profile-avatar">
            ${
              user.picture
                ? `<img src="${user.picture}" alt="Profile" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover;">`
                : '<div style="width: 80px; height: 80px; border-radius: 50%; background: #e5e7eb; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #6b7280;">👤</div>'
            }
          </div>
          <div class="profile-info">
            <h4>${user.name || "N/A"}</h4>
            <p style="color: #6b7280; margin: 5px 0;">Expert Account</p>
            <div class="approval-badge ${user.approved ? "approved" : "pending"}">
              ${user.approved ? "✅ Approved" : "⏳ Pending Approval"}
            </div>
          </div>
        </div>
        
        <div class="profile-details">
          <div class="detail-item">
            <label>Full Name:</label>
            <span>${user.name || "N/A"}</span>
          </div>
          <div class="detail-item">
            <label>Department:</label>
            <span>${user.department || "N/A"}</span>
          </div>
        </div>
      </div>
      
      <style>
        .profile-section {
          padding: 20px 0;
        }
        
        .profile-header {
          display: flex;
          align-items: center;
          gap: 20px;
          margin-bottom: 30px;
          padding-bottom: 20px;
          border-bottom: 1px solid #e5e7eb;
        }
        
        .profile-avatar {
          flex-shrink: 0;
        }
        
        .profile-info h4 {
          margin: 0 0 5px 0;
          font-size: 20px;
          color: #111827;
        }
        
        .approval-badge {
          display: inline-block;
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
          margin-top: 8px;
        }
        
        .approval-badge.approved {
          background: #d1fae5;
          color: #065f46;
        }
        
        .approval-badge.pending {
          background: #fed7aa;
          color: #92400e;
        }
        
        .profile-details {
          display: flex;
          flex-direction: column;
          gap: 15px;
        }
        
        .detail-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 0;
          border-bottom: 1px solid #f3f4f6;
        }
        
        .detail-item label {
          font-weight: 500;
          color: #374151;
          min-width: 120px;
        }
        
        .detail-item span {
          color: #6b7280;
          word-break: break-all;
        }
        
        .status.approved {
          color: #059669;
          font-weight: 500;
        }
        
        .status.pending {
          color: #d97706;
          font-weight: 500;
        }
      </style>
    `;
    })
    .catch((error) => {
      console.error("Error loading profile:", error);
      profileContent.innerHTML =
        '<p style="color: red;">Error loading profile</p>';
    });
}

// ----------------------------
// LOAD FUNCTIONS
// ----------------------------

function loadAssignedTasks() {
  // Placeholder for assigned tasks loading
  const container = document.querySelector("#assignedTasksContainer");
  if (container) {
    container.innerHTML = '<p class="empty">No tasks assigned yet.</p>';
  }
}

function loadEarnings() {
  // Placeholder for earnings loading
  const earningsElement = document.querySelector(".earnings");
  if (earningsElement) {
    earningsElement.textContent = "₹0.00";
  }
}

// ===============================
// ADMIN - PENDING EXPERTS
// ===============================

async function loadPendingExperts() {
  const res = await apiRequest("/admin/experts/pending");

  if (!res.ok) {
    console.error(res.data.error);
    return;
  }

  const tableBody = document.querySelector("#expertTable tbody");
  tableBody.innerHTML = "";

  if (res.data.experts.length === 0) {
    tableBody.innerHTML = "<tr><td colspan='4'>No pending experts</td></tr>";
    return;
  }

  res.data.experts.forEach((exp) => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${exp.name}</td>
      <td>${exp.email}</td>
      <td>${exp.department}</td>
      <td>
        <button onclick="approveExpert('${exp.expert_id}')">
          Approve
        </button>
      </td>
    `;

    tableBody.appendChild(row);
  });
}

async function approveExpert(expertId) {
  const res = await apiRequest(`/admin/experts/approve/${expertId}`, "POST");

  if (!res.ok) {
    alert(res.data.error || "Approval failed");
    return;
  }

  alert("Expert approved!");
  loadPendingExperts();
}

// ===============================
// EXPERT DASHBOARD PROFILE
// ===============================

async function loadExpertProfile() {
  try {
    const res = await apiRequest("/me");

    if (!res.ok) {
      alert("Session expired. Please login again.");
      window.location.href = "/public/login.html";
      return;
    }

    const user = res.data;

    if (user.role.includes("Expert")) {
      if (user.approved) {
        showApprovedUI();
        loadAvailableQuestions(); // only load if approved
      } else {
        showPendingApprovalUI();
      }
    }
  } catch (error) {
    console.error("Error loading expert profile:", error);
    alert("Error loading profile. Please refresh the page.");
  }
}

function showPendingApprovalUI() {
  const approvalStatus = document.getElementById("approvalStatus");
  const assignmentSection = document.getElementById("assignmentSection");

  if (approvalStatus) {
    approvalStatus.innerHTML =
      "<p style='color:orange;'>Your account is pending admin approval.</p>";
  }

  if (assignmentSection) {
    assignmentSection.style.display = "none";
  }
}

function showApprovedUI() {
  const approvalStatus = document.getElementById("approvalStatus");
  const assignmentSection = document.getElementById("assignmentSection");

  if (approvalStatus) {
    approvalStatus.innerHTML =
      "<p style='color:green;'>Your account is approved.</p>";
  }

  if (assignmentSection) {
    assignmentSection.style.display = "block";
  }
}

// ===============================
// AVAILABLE QUESTIONS (PHASE A)
// ===============================

async function loadAvailableQuestions() {
  const res = await apiRequest("/expert/questions/available");

  if (!res.ok) {
    console.error(res.data.error);
    return;
  }

  const list = document.getElementById("availableQuestions");
  list.innerHTML = "";

  if (!res.data.questions || res.data.questions.length === 0) {
    list.innerHTML = "<li>No available questions</li>";
    return;
  }

  res.data.questions.forEach((q) => {
    const li = document.createElement("li");

    let buttonHTML;

    // 🔥 IMPORTANT: Check if already applied
    if (q.has_applied) {
      buttonHTML = `
        <button disabled 
                style="background:#9ca3af; cursor:not-allowed;">
          Applied
        </button>
      `;
    } else {
      buttonHTML = `
        <button onclick="expressInterest('${q.question_id}', this)">
          I WANT TO SOLVE
        </button>
      `;
    }

    li.innerHTML = `
      <div style="margin-bottom:15px;">
        <strong>${q.title}</strong><br/>
        <small>${q.description}</small><br/>
        ${buttonHTML}
      </div>
    `;

    list.appendChild(li);
  });
}

// ===============================
// EXPRESS INTEREST
// ===============================

async function expressInterest(questionId, btn) {
  btn.disabled = true;
  btn.innerText = "Applying...";

  const res = await apiRequest(
    `/expert/questions/interest/${questionId}`,
    "POST",
  );

  if (!res.ok) {
    btn.disabled = false;
    btn.innerText = "I WANT TO SOLVE";
    alert(res.data.error || "Failed to register interest");
    return;
  }

  // Update button immediately
  btn.innerText = "Applied";
  btn.style.background = "#9ca3af";
}

// ===============================
// LOGOUT
// ===============================

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.location.href = "/";
}

// ===============================
// INIT
// ===============================

document.addEventListener("DOMContentLoaded", () => {
  loadExpertProfile();
});
