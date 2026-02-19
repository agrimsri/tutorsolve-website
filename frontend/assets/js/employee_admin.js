// ===============================
// ALL QUESTIONS (Default)
// ===============================
let currentStudentView = null;

function stopAllChatActivity() {
  // Clear order polling
  if (window.chatInterval) {
    clearInterval(window.chatInterval);
    window.chatInterval = null;
  }

  // Clear question polling
  if (window.questionChatInterval) {
    clearInterval(window.questionChatInterval);
    window.questionChatInterval = null;
  }
}

function showAllQuestions() {
  const container = document.getElementById("employeeContent");
  stopAllChatActivity();

  container.innerHTML = `
    <div class="card">
      <h3>All Questions</h3>
      <div class="filter-controls">
        <select id="statusFilter" onchange="filterQuestions()">
          <option value="">All Status</option>
          <option value="CREATED">Created</option>
          <option value="ASSIGNED">Assigned</option>
          <option value="NEGOTIATION">Negotiation</option>
          <option value="IN_PROGRESS">In Progress</option>
          <option value="COMPLETED">Completed</option>
        </select>
        <button onclick="refreshQuestions()">Refresh</button>
      </div>
      <div id="questionsTable">
        <p>Loading...</p>
      </div>
    </div>
  `;

  // Check user role before loading
  checkEmployeeAdminAuth();
  loadAllQuestions();
}

function checkEmployeeAdminAuth() {
  // Check current user authentication and role
  apiRequest("/me")
    .then((res) => {
      if (!res.ok) {
        console.error("Auth check failed:", res.data);
        return;
      }

      const user = res.data;

      if (!user.role.includes("EmployeeAdmin")) {
        console.warn("User is not an EmployeeAdmin! Role:", user.role);
        alert("Access denied: You are not an Employee Admin");
      }
    })
    .catch((error) => {
      console.error("Error checking auth:", error);
    });
}

async function loadAllQuestions(status = null) {
  const container = document.getElementById("questionsTable");
  if (!container) return;

  container.innerHTML = "<p>Loading...</p>";

  const res = await apiRequest("/employee-admin/questions/");
  console.log("Negotiations:", res);

  if (!res.ok) {
    container.innerHTML = "<p>Error loading data</p>";
    return;
  }

  if (res.data.questions.length === 0) {
    container.innerHTML = "<p>No questions found</p>";
    return;
  }

  const questions = res.data.questions;

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Department</th>
          <th>Student</th>
          <th>Status</th>
          <th>Interested</th>
          <th>Assigned Expert</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${questions
          .map(
            (q) => `
          <tr>
            <td>${q.title}</td>
            <td>${q.department || "N/A"}</td>
            <td>${q.student_name}</td>
            <td><span class="status-badge ${q.status?.toLowerCase()}">${q.status}</span></td>
            <td>${q.interested_count || 0}</td>
            <td>${q.assigned_expert || "Not assigned"}</td>
            <td>
              ${
                q.status === "CREATED"
                  ? `<button onclick="viewQuestionDetail('${q.question_id}')">Review</button>`
                  : ""
              }
              ${
                q.status === "ASSIGNED" && q.interested_count > 0
                  ? `<button onclick="viewInterestedExperts('${q.question_id}')">View Experts</button>`
                  : ""
              }
              ${
                q.status === "NEGOTIATION"
                  ? `<button onclick="showNegotiation('${q.question_id}')">Manage</button>`
                  : ""
              }
              ${
                q.status === "UNDER_REVIEW"
                  ? `<button onclick="viewQuestionDetail('${q.question_id}')">Details</button>`
                  : ""
              }
              ${
                q.status === "PRICING_PENDING_APPROVAL"
                  ? `<button onclick="showNegotiation('${q.question_id}')">Manage</button>`
                  : ""
              }
            </td>
          </tr>
        `,
          )
          .join("")}
      </tbody>
    </table>

    <style>
      .filter-controls {
        margin-bottom: 16px;
        display: flex;
        gap: 12px;
        align-items: center;
      }
      
      .filter-controls select {
        padding: 8px 12px;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        font-size: 14px;
      }
      
      .filter-controls button {
        padding: 8px 16px;
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        cursor: pointer;
      }
      
      .filter-controls button:hover {
        background: #2563eb;
      }
      
      .status-badge {
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
      }
      
      .status-badge.created {
        background: #fef3c7;
        color: #92400e;
      }
      
      .status-badge.under_review {
        background: #e9d5ff;
        color: #7c3aed;
      }
      
      .status-badge.assigned {
        background: #dbeafe;
        color: #1e40af;
      }
      
      .status-badge.negotiation {
        background: #e9d5ff;
        color: #7c3aed;
      }
      
      .status-badge.in_progress {
        background: #fef3c7;
        color: #92400e;
      }
      
      .status-badge.completed {
        background: #dcfce7;
        color: #166534;
      }
      
      table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 16px;
      }
      
      th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #e5e7eb;
      }
      
      th {
        background: #f9fafb;
        font-weight: 600;
        color: #374151;
      }
      
      td button {
        margin-right: 8px;
        padding: 4px 8px;
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 12px;
        cursor: pointer;
      }
      
      td button:hover {
        background: #2563eb;
      }
    </style>
  `;
}

function filterQuestions() {
  const status = document.getElementById("statusFilter").value;
  loadAllQuestions(status);
}

function refreshQuestions() {
  const status = document.getElementById("statusFilter").value;
  loadAllQuestions(status);
}

function startNegotiation(questionId) {
  apiRequest(
    `/employee-admin/questions/start-negotiation/${questionId}`,
    "POST",
  )
    .then(() => {
      // Refresh the question detail view to update the status and remove the button
      viewQuestionDetail(questionId);
    })
    .catch((error) => {
      console.error("Error starting negotiation:", error);
      alert("Failed to start negotiation");
    });
}

async function viewQuestionDetail(questionId) {
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

  if (q.status === "CREATED") {
    const review_res = await apiRequest(
      `/employee-admin/questions/start-review/${questionId}`,
      "POST",
    );
    q.status = "UNDER_REVIEW";
  }

  container.innerHTML = `
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div style="flex: 1;">
          <h3>${q.title}</h3>
          <p><strong>Department:</strong> ${q.department}</p>
          <p><strong>Student:</strong> ${q.student_name}</p>
          <p><strong>Status:</strong> ${q.status}</p>
          <p>${q.description}</p>
        </div>
        <div style="margin-left: 20px;">
          ${
            q.status === "UNDER_REVIEW"
              ? `<button onclick="startNegotiation('${q.question_id}')" style="background: #8b5cf6; color: white; padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer;">Start Negotiation</button>`
              : ""
          }
        </div>
      </div>
    </div>

    ${
      q.interested_experts && q.interested_experts.length > 0
        ? `
      <div class="card">
        <h3>Interested Experts</h3>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Department</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${q.interested_experts
              .map(
                (exp) => `
              <tr>
                <td>${exp.name}</td>
                <td>${exp.email}</td>
                <td>${exp.department}</td>
                <td>
                  <button onclick="selectExpert('${q.question_id}', '${exp.expert_id}')">
                    Select Expert
                  </button>
                </td>
              </tr>
            `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
      `
        : ""
    }

    <button onclick="showAllQuestions()">← Back to Questions</button>
  `;
}

async function selectExpert(questionId, expertId) {
  if (!confirm("Start negotiation with this expert?")) return;

  const res = await apiRequest(
    "/employee-admin/orders/create-from-interest",
    "POST",
    {
      questionId: questionId,
      expertId: expertId,
    },
  );

  if (!res.ok) {
    alert(res.data.error || "Failed to create order");
    return;
  }

  showNegotiation(res.data.order_id);
}

async function assignExpertToNegotiation(orderId, expertId, expertName) {
  if (!confirm(`Assign ${expertName} to this negotiation?`)) return;

  try {
    const res = await apiRequest(
      `/employee-admin/orders/${orderId}/assign-expert`,
      "POST",
      {
        expertId: expertId,
      },
    );

    if (!res.ok) {
      alert(res.data.error || "Failed to assign expert");
      return;
    }

    alert("Expert assigned successfully!");
    // Refresh the negotiation view to show the updated assignment
    showNegotiation(orderId);
  } catch (error) {
    console.error("Error assigning expert:", error);
    alert("Failed to assign expert");
  }
}

// ===============================
// INTERESTED QUESTIONS (Legacy)
// ===============================

function showInterestedQuestions() {
  const container = document.getElementById("employeeContent");
  stopAllChatActivity();

  container.innerHTML = `
    <div class="card">
      <h3>Interested Questions</h3>
      <div id="interestedTable">
        <p>Loading...</p>
      </div>
    </div>
  `;

  loadInterestedQuestions();
}

async function loadInterestedQuestions() {
  const container = document.getElementById("interestedTable");
  if (!container) return;

  container.innerHTML = "<p>Loading...</p>";

  const res = await apiRequest("/employee-admin/questions/interested");

  if (!res.ok) {
    container.innerHTML = "<p>Error loading data</p>";
    return;
  }

  if (res.data.questions.length === 0) {
    container.innerHTML = "<p>No interested questions</p>";
    return;
  }

  container.innerHTML = `
    <table>
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
        ${res.data.questions
          .map(
            (q) => `
          <tr>
            <td>${q.title}</td>
            <td>${q.department}</td>
            <td>${q.student_name}</td>
            <td>${q.interested_count}</td>
            <td>
              <button onclick="viewInterestedExperts('${q.question_id}')">
                View
              </button>
            </td>
          </tr>
        `,
          )
          .join("")}
      </tbody>
    </table>
  `;
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

    <button onclick="showAllQuestions()">← Back to Questions</button>
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

function loadMyOrders() {
  // Placeholder for orders loading
  const container = document.querySelector("#ordersContainer");
  if (container) {
    container.innerHTML = '<p class="empty">No active orders yet.</p>';
  }
}

function showActiveOrders() {
  const container = document.getElementById("employeeContent");
  stopAllChatActivity();

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
  stopAllChatActivity();

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
  stopAllChatActivity();

  container.innerHTML = `
    <div class="card">
      <h3>Completed Orders</h3>
      <p class="empty">No completed orders yet.</p>
    </div>
  `;
}

// ===============================
// PROFILE
// ===============================

function showProfile() {
  const container = document.getElementById("employeeContent");
  stopAllChatActivity();

  container.innerHTML = `
    <div class="card">
      <h3>Employee Admin Profile</h3>
      <div id="profileContent">
        <p>Loading profile...</p>
      </div>
    </div>
  `;

  loadEmployeeProfile();
}

function loadEmployeeProfile() {
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
            <p style="color: #6b7280; margin: 5px 0;">Employee Admin Account</p>
            <div class="role-badge employee-admin">
              Employee Admin
            </div>
          </div>
        </div>
        
        <div class="profile-details">
          <div class="detail-item">
            <label>Full Name:</label>
            <span>${user.name || "N/A"}</span>
          </div>
          <div class="detail-item">
            <label>Email:</label>
            <span>${user.email || "N/A"}</span>
          </div>
          <div class="detail-item">
            <label>Role:</label>
            <span>${user.role.join(", ")}</span>
          </div>
          <div class="detail-item">
            <label>User ID:</label>
            <span>${user.user_id}</span>
          </div>
          <div class="detail-item">
            <label>Account Status:</label>
            <span class="status-badge active">Active</span>
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
        
        .role-badge {
          display: inline-block;
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
          margin-top: 8px;
        }
        
        .role-badge.employee-admin {
          background: #dbeafe;
          color: #1e40af;
        }
        
        .status-badge {
          display: inline-block;
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }
        
        .status-badge.active {
          background: #dcfce7;
          color: #166534;
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

// ===============================
// LOGOUT
// ===============================

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.location.href = "/";
}

// ===============================
// NEGOTIATIONS
// ===============================

function showNegotiations() {
  const container = document.getElementById("employeeContent");
  stopAllChatActivity();

  container.innerHTML = `
    <div class="card">
      <h3>Active Negotiations</h3>
      <div id="negotiationsList">
        <p>Loading negotiations...</p>
      </div>
    </div>
  `;

  loadNegotiations();
}

async function loadNegotiations() {
  const container = document.getElementById("negotiationsList");
  if (!container) return;

  container.innerHTML = "<p>Loading negotiations...</p>";

  try {
    // Get orders with status "NEGOTIATION"
    const res = await apiRequest("/employee-admin/questions/negotiations");

    if (!res.ok) {
      container.innerHTML =
        '<p style="color: red;">Failed to load negotiations</p>';
      return;
    }

    const negotiations = res.data.negotiations || [];

    if (negotiations.length === 0) {
      container.innerHTML = '<p class="empty">No active negotiations</p>';
      return;
    }

    container.innerHTML = `
      <div class="negotiations-list">
        ${negotiations
          .map(
            (negotiation) => `
          <div class="negotiation-item">
            <div class="negotiation-header">
              <h4>${negotiation.question.title}</h4>
              <span class="expert-count">${negotiation.question.interested_experts.length} Expert${negotiation.question.interested_experts.length !== 1 ? "s" : ""} Interested</span>
            </div>
            <div class="negotiation-details">
              <p><strong>Student:</strong> ${negotiation.student.name}</p>
              <p><strong>Department:</strong> ${negotiation.question.department}</p>
              <p><strong>Status:</strong> ${negotiation.question.status}</p>
              <p><strong>Created:</strong> ${new Date(negotiation.question.created_at).toLocaleDateString()}</p>
            </div>
            <div class="negotiation-actions">
              <button onclick="showNegotiation('${negotiation._id}')">
                Manage Negotiation
              </button>
            </div>
          </div>
        `,
          )
          .join("")}
      </div>

      <style>
        .negotiations-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
          margin-top: 16px;
        }
        
        .negotiation-item {
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 16px;
          background: #f9fafb;
        }
        
        .negotiation-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        
        .negotiation-header h4 {
          margin: 0;
          color: #111827;
          font-size: 16px;
          flex: 1;
        }
        
        .expert-count {
          background: #10b981;
          color: white;
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }
        
        .status-badge {
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }
        
        .status-badge.negotiation {
          background: #e9d5ff;
          color: #7c3aed;
        }
        
        .negotiation-details {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 12px;
        }
        
        .negotiation-details p {
          margin: 0;
          font-size: 14px;
          color: #6b7280;
        }
        
        .negotiation-details strong {
          color: #374151;
        }
        
        .negotiation-actions {
          display: flex;
          gap: 8px;
        }
        
        .negotiation-actions button {
          background: #3b82f6;
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 14px;
          cursor: pointer;
          transition: background 0.2s ease;
        }
        
        .negotiation-actions button:hover {
          background: #2563eb;
        }
      </style>
    `;
  } catch (error) {
    console.error("Error loading negotiations:", error);
    container.innerHTML =
      '<p style="color: red;">Error loading negotiations</p>';
  }
}

async function submitPricing(questionId) {
  const studentPrice = document.getElementById("studentPrice").value;
  const expertPayout = document.getElementById("expertPayout").value;
  const validationDiv = document.getElementById("pricingValidation");

  if (!studentPrice || !expertPayout) {
    validationDiv.className = "pricing-validation error";
    validationDiv.textContent = "Both pricing fields are required";
    validationDiv.style.display = "block";
    return;
  }

  if (parseFloat(expertPayout) >= parseFloat(studentPrice)) {
    validationDiv.className = "pricing-validation error";
    validationDiv.textContent = "Expert payout must be less than student price";
    validationDiv.style.display = "block";
    return;
  }

  // Show loading state
  validationDiv.className = "pricing-validation info";
  validationDiv.textContent = "Submitting pricing...";
  validationDiv.style.display = "block";

  const res = await apiRequest(
    `/employee-admin/questions/${questionId}/pricing`,
    "POST",
    {
      studentPrice: parseFloat(studentPrice),
      expertPayout: parseFloat(expertPayout),
    },
  );

  if (!res.ok) {
    validationDiv.className = "pricing-validation error";
    validationDiv.textContent = res.data?.error || "Failed to submit pricing";
    validationDiv.style.display = "block";
    return;
  }

  // Show success message
  validationDiv.className = "pricing-validation success";
  validationDiv.textContent = "✓ Pricing submitted successfully for approval";
  validationDiv.style.display = "block";

  // Clear form
  document.getElementById("studentPrice").value = "";
  document.getElementById("expertPayout").value = "";

  // Reload negotiation view to show pricing request details
  setTimeout(() => {
    showNegotiation(questionId);
  }, 1500);
}

async function showNegotiation(negotiationId) {
  const container = document.getElementById("employeeContent");

  container.innerHTML = `
    <button class="back-btn-black" onclick="showNegotiations()">← Back to Negotiations</button>
    
    <div class="card">
      <h3>Loading negotiation details...</h3>
    </div>
  `;

  const res = await apiRequest(
    `/employee-admin/questions/negotiations/${negotiationId}`,
  );
  question = res.data.negotiation.question;
  student = res.data.negotiation.student;

  if (!res.ok) {
    container.innerHTML = `
      <div class="card">
        <p>Error loading order.</p>
      </div>
    `;
    return;
  }

  // Check if there are interested experts for this question
  let interestedExpertsSection = "";
  if (question.interested_experts && question.interested_experts.length > 0) {
    interestedExpertsSection = `
      <!-- INTERESTED EXPERTS -->
      <div class="card">
        <h3>Interested Experts</h3>
        <div class="experts-grid">
          ${question.interested_experts
            .map(
              (expert) => `
            <div class="expert-card">
              <div class="expert-info">
                <h4>${expert.name}</h4>
                <p><strong>Email:</strong> ${expert.email}</p>
                <p><strong>Department:</strong> ${expert.department}</p>
              </div>
              <div class="expert-actions">
                <button onclick="assignExpertToNegotiation('${question._id}', '${expert.expert_id}', '${expert.name}')" 
                        class="assign-btn">
                  Assign Expert
                </button>
              </div>
            </div>
          `,
            )
            .join("")}
        </div>
      </div>
    `;
  }

  container.innerHTML = `
    <button class="back-btn-black" onclick="showNegotiations()">← Back to Negotiations</button>

    <!-- QUESTION SUMMARY -->
    <div class="card">
      <h3>${question.title}</h3>
      <p><strong>Department:</strong> ${question.department}</p>
      <p><strong>Student:</strong> ${student.name}</p>
      <p>${question.description}</p>
    </div>

    <!-- CURRENTLY ASSIGNED EXPERT (if any) -->
    ${
      question.expert
        ? `
      <div class="card">
        <h3>Currently Assigned Expert</h3>
        <div class="expert-card assigned">
          <div class="expert-info">
            <h4>${question.expert.name}</h4>
            <p><strong>Email:</strong> ${question.expert.email}</p>
            <p><strong>Department:</strong> ${question.expert.department}</p>
          </div>
          <div class="expert-status">
            <span class="status-badge assigned">✓ Assigned</span>
          </div>
        </div>
      </div>
    `
        : ""
    }

    ${interestedExpertsSection}

    <!-- PRICING SECTION -->
    ${
      res.data.negotiation.pricing_request
        ? `
          <!-- PRICING REQUEST DETAILS -->
          <div class="pricing-form">
            <h3>📋 Pricing Request Details</h3>
            
            <div class="pricing-details">
              <div class="detail-row">
                <label>Student Price:</label>
                <span class="price-value">$${res.data.negotiation.pricing_request.studentPrice}</span>
              </div>
              
              <div class="detail-row">
                <label>Expert Payout:</label>
                <span class="price-value">$${res.data.negotiation.pricing_request.expertPayout}</span>
              </div>
              
              <div class="detail-row">
                <label>Status:</label>
                <span class="status-badge ${res.data.negotiation.pricing_request.status === "APPROVED" ? "status-approved" : "status-pending"}">
                  ${res.data.negotiation.pricing_request.status === "APPROVED" ? "✓ Approved" : "⏳ Pending Approval"}
                </span>
              </div>
            </div>
          </div>
        `
        : `
          <!-- PRICING FORM -->
          <div class="pricing-form">
            <h3>Set Pricing</h3>

            <div class="pricing-inputs">
              <div class="pricing-input-group">
                <label>
                  <span class="price-icon">👨‍🎓</span>
                  Student Price:
                </label>
                <input type="number" id="studentPrice"
                       value="${question.studentPrice || ""}" 
                       placeholder="0.00"
                       step="0.01"
                       min="0" />
              </div>

              <div class="pricing-input-group">
                <label>
                  <span class="price-icon">👨‍💼</span>
                  Expert Payout:
                </label>
                <input type="number" id="expertPayout"
                       value="${question.expertPayout || ""}" 
                       placeholder="0.00"
                       step="0.01"
                       min="0" />
              </div>
            </div>

            <div class="pricing-validation" id="pricingValidation"></div>

            <button class="pricing-submit-btn" onclick="submitPricing('${question._id}')">
              Submit Pricing
            </button>
          </div>
        `
    }

    <!-- STUDENT CHAT -->
    <div class="card">
      <h3>Student Communication</h3>

      <div id="questionChatContainer">
        <div class="chat-messages" id="chatBox">
        </div>

        <div class="chat-input-container">
          <input type="text" id="chatInput"
                 placeholder="Type your message..." />
          <button onclick="sendChatMessage('${question._id}')">
            Send
          </button>
        </div>
      </div>
    </div>
  `;

  // Add beautiful chat styling from student dashboard
  // const style = document.createElement("style");
  // style.textContent = `

  // `;
  // document.head.appendChild(style);

  // Store question ID locally to avoid scoping issues
  const questionId = question._id;

  loadChat(questionId);

  // Optional: auto refresh chat every 5 seconds
  if (window.chatInterval) clearInterval(window.chatInterval);
  console.log("Starting chat polling for question:", questionId);
  window.chatInterval = setInterval(() => {
    console.log("Chat polling tick for question:", questionId);
    loadChat(questionId);
  }, 5000);

  // Add enter key support for chat input
  document
    .getElementById("chatInput")
    .addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        sendChatMessage(questionId);
      }
    });
}

// ===============================
// CHAT FUNCTIONALITY FOR EMPLOYEE ADMIN
// ===============================

async function loadChat(orderId) {
  try {
    console.log("Loading chat for question:", orderId);
    const res = await apiRequest(`/employee-admin/questions/${orderId}/chat`);

    if (!res.ok) {
      console.error("Failed to load chat messages:", res.data);
      return;
    }

    const messages = res.data.messages || [];
    const chatBox = document.getElementById("chatBox");

    if (!chatBox) {
      console.log("Chat box not found in DOM");
      return;
    }

    console.log("Loaded messages:", messages.length);

    // ===== SMART SCROLL LOGIC START =====
    const threshold = 60;
    const isNearBottom =
      chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <
      threshold;
    const previousScrollHeight = chatBox.scrollHeight;
    const previousScrollTop = chatBox.scrollTop;
    // ===== SMART SCROLL LOGIC END =====

    if (messages.length === 0) {
      chatBox.innerHTML =
        '<p style="color: #6b7280; text-align: center;">No messages yet. Start the conversation!</p>';
      return;
    }

    chatBox.innerHTML = messages
      .map((msg) => {
        const isAdmin = msg.senderRole === "EmployeeAdmin";
        const isStudent = msg.senderRole === "Student";
        const isExpert = msg.senderRole === "Expert";

        let senderName = "Unknown";
        let messageClass = "chat-message-other";

        if (isAdmin) {
          senderName = "You (Admin)";
          messageClass = "chat-message-admin";
        } else if (isStudent) {
          senderName = "Student";
          messageClass = "chat-message-student";
        } else if (isExpert) {
          senderName = "Expert";
          messageClass = "chat-message-expert";
        }

        const time = new Date(msg.createdAt).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        return `
          <div class="chat-message ${messageClass}">
            <div class="sender">${senderName}</div>
            <div class="message-text">${msg.message}</div>
            <div class="timestamp">${time}</div>
          </div>
        `;
      })
      .join("");

    // ===== SMART SCROLL LOGIC CONTINUED =====
    if (isNearBottom) {
      // User was at bottom → keep auto-scroll
      chatBox.scrollTop = chatBox.scrollHeight;
    } else {
      // User was reading old messages → preserve position
      const newScrollHeight = chatBox.scrollHeight;
      chatBox.scrollTop =
        previousScrollTop + (newScrollHeight - previousScrollHeight);
    }
  } catch (error) {
    console.error("Error loading chat messages:", error);
  }
}

async function sendChatMessage(questionId) {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();

  if (!message) return;

  try {
    const res = await apiRequest(
      `/employee-admin/questions/${questionId}/chat`,
      "POST",
      { message },
    );

    if (!res.ok) {
      alert(res.data?.error || "Failed to send message");
      return;
    }

    // Clear input and refresh messages
    input.value = "";
    loadChat(questionId);
  } catch (error) {
    console.error("Error sending message:", error);
    alert("Failed to send message");
  }
}

// ===============================
// QUESTION CHAT FUNCTIONALITY FOR ADMIN
// ===============================

async function loadQuestionChatMessages(questionId) {
  try {
    const res = await apiRequest(
      `/employee-admin/questions/${questionId}/chat`,
    );

    if (!res.ok) {
      console.error("Failed to load question messages:", res.data);
      return;
    }

    const messages = res.data.messages || [];
    const messagesContainer = document.getElementById("questionChatMessages");

    if (!messagesContainer) return;

    // ===== SMART SCROLL LOGIC START =====
    const threshold = 60;
    const isNearBottom =
      messagesContainer.scrollHeight -
        messagesContainer.scrollTop -
        messagesContainer.clientHeight <
      threshold;
    const previousScrollHeight = messagesContainer.scrollHeight;
    const previousScrollTop = messagesContainer.scrollTop;
    // ===== SMART SCROLL LOGIC END =====

    if (messages.length === 0) {
      messagesContainer.innerHTML =
        '<p style="color: #6b7280; text-align: center;">No messages yet. Start the conversation!</p>';
      return;
    }

    messagesContainer.innerHTML = messages
      .map((msg) => {
        const isAdmin = msg.senderRole === "EmployeeAdmin";
        const isStudent = msg.senderRole === "Student";
        const isExpert = msg.senderRole === "Expert";

        let senderName;
        if (isAdmin) senderName = "You (Admin)";
        else if (isStudent) senderName = "Student";
        else if (isExpert) senderName = "Expert";
        else senderName = "Unknown";

        const time = new Date(msg.createdAt).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        let messageClass;
        if (isAdmin) messageClass = "chat-message-admin";
        else if (isStudent) messageClass = "chat-message-student";
        else if (isExpert) messageClass = "chat-message-expert";

        return `
          <div class="chat-message ${messageClass}">
            <div class="sender">${senderName}</div>
            <div class="message-text">${msg.message}</div>
            <div class="timestamp">${time}</div>
          </div>
        `;
      })
      .join("");

    // ===== SMART SCROLL LOGIC CONTINUED =====
    if (isNearBottom) {
      // User was at bottom → keep auto-scroll
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    } else {
      // User was reading old messages → preserve position
      const newScrollHeight = messagesContainer.scrollHeight;
      messagesContainer.scrollTop =
        previousScrollTop + (newScrollHeight - previousScrollHeight);
    }
  } catch (error) {
    console.error("Error loading question chat messages:", error);
  }
}

async function sendQuestionChatMessage(questionId) {
  const input = document.getElementById("questionChatInput");
  const message = input.value.trim();

  if (!message) return;

  try {
    const res = await apiRequest(
      `/employee-admin/questions/${questionId}/chat`,
      "POST",
      { message },
    );

    if (!res.ok) {
      alert(res.data?.error || "Failed to send message");
      return;
    }

    // Clear input and refresh messages
    input.value = "";
    loadQuestionChatMessages(questionId);
  } catch (error) {
    console.error("Error sending question chat message:", error);
    alert("Failed to send message");
  }
}

// ===============================
// PRICING FUNCTIONALITY
// ===============================

async function submitPricing(questionId) {
  const studentPrice = document.getElementById("studentPrice").value;
  const expertPayout = document.getElementById("expertPayout").value;

  if (!studentPrice || !expertPayout) {
    alert("Please fill in both pricing fields");
    return;
  }

  try {
    const res = await apiRequest(
      `/employee-admin/questions/${questionId}/pricing`,
      "POST",
      {
        studentPrice: parseFloat(studentPrice),
        expertPayout: parseFloat(expertPayout),
      },
    );

    if (!res.ok) {
      alert(res.data?.error || "Failed to submit pricing");
      return;
    }

    alert("Pricing submitted successfully!");

    // Reload negotiation view to show pricing request details
    setTimeout(() => {
      showNegotiation(questionId);
    }, 1000);
  } catch (error) {
    console.error("Error submitting pricing:", error);
    alert("Failed to submit pricing");
  }
}
