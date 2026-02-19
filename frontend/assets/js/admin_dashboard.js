function loadView(view) {
  const container = document.getElementById("adminContent");

  if (!container) return;

  switch (view) {
    case "experts":
      container.innerHTML = getExpertsView();
      loadPendingExperts();
      loadAllExperts();
      break;

    case "pricing-requests":
      container.innerHTML = getPricingRequestsView();
      loadPricingRequests();
      break;

    case "students":
      container.innerHTML = getStudentsView();
      loadStudents();
      break;

    case "employee-admins":
      container.innerHTML = getEmployeeAdminsView();
      loadEmployeeAdmins();
      break;

    case "dashboard":
      container.innerHTML = getDashboardView();
      loadDashboardStats();
      break;

    case "create-employee-admin":
      container.innerHTML = getCreateEmployeeAdminView();
      loadEmployeeDepartments(); // Load departments dynamically
      break;

    default:
      container.innerHTML = "<p>Page not found</p>";
  }
}

// ----------------------------
// VIEW TEMPLATES
// ----------------------------

function getExpertsView() {
  return `
    <div class="card">
      <h3>Experts Management</h3>
      
      <div class="tabs">
        <button class="tab-btn active" onclick="showExpertTab('pending')">Pending Approval</button>
        <button class="tab-btn" onclick="showExpertTab('all')">All Experts</button>
      </div>

      <!-- Pending Experts Tab -->
      <div id="pendingTab" class="tab-content">
        <h4>Pending Expert Approvals</h4>
        <table id="pendingExpertTable">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Department</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
        <p id="pendingEmptyState" class="empty" style="display:none;">
          No pending expert approvals.
        </p>
      </div>

      <!-- All Experts Tab -->
      <div id="allTab" class="tab-content" style="display:none;">
        <h4>All Experts</h4>
        <table id="allExpertTable">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Department</th>
              <th>Mobile</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
        <p id="allEmptyState" class="empty" style="display:none;">
          No experts found.
        </p>
      </div>
    </div>

    <style>
      .tabs {
        display: flex;
        gap: 10px;
        margin-bottom: 20px;
        border-bottom: 2px solid #e2e8f0;
      }
      
      .tab-btn {
        background: none;
        border: none;
        padding: 10px 20px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        color: #64748b;
        border-bottom: 2px solid transparent;
        transition: all 0.3s ease;
      }
      
      .tab-btn.active {
        color: #3b82f6;
        border-bottom-color: #3b82f6;
      }
      
      .tab-btn:hover {
        color: #3b82f6;
      }
      
      .tab-content {
        margin-top: 20px;
      }
      
      .tab-content h4 {
        margin: 0 0 15px 0;
        color: #1e293b;
        font-size: 16px;
      }
      
      table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
      }
      
      th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #e2e8f0;
      }
      
      th {
        background-color: #f8fafc;
        font-weight: 600;
        color: #374151;
      }
      
      .status-badge {
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
      }
      
      .status-approved {
        background-color: #dcfce7;
        color: #166534;
      }
      
      .status-pending {
        background-color: #fef3c7;
        color: #92400e;
      }
      
      .btn-approve {
        background-color: #10b981;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      }
      
      .btn-approve:hover {
        background-color: #059669;
      }
      
      .btn-view {
        background-color: #3b82f6;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      }
      
      .btn-view:hover {
        background-color: #2563eb;
      }
    </style>
  `;
}

function getStudentsView() {
  return `
    <div class="card">
      <h3>All Students</h3>
      
      <table id="studentsTable">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th>Registered</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
      
      <p id="studentsEmptyState" class="empty" style="display:none;">
        No students found.
      </p>
    </div>
  `;
}

function getEmployeeAdminsView() {
  return `
    <div class="card">
      <h3>All Employee Admins</h3>
      
      <table id="employeeAdminsTable">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Mobile</th>
            <th>Status</th>
            <th>Registered</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
      
      <p id="employeeAdminsEmptyState" class="empty" style="display:none;">
        No employee admins found.
      </p>
    </div>
  `;
}

function getPricingRequestsView() {
  return `
    <div class="card">
      <h3>Pricing Requests</h3>
      
      <table id="pricingRequestsTable">
        <thead>
          <tr>
            <th>Question ID</th>
            <th>Student Price</th>
            <th>Expert Payout</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
      
      <p id="pricingRequestsEmptyState" class="empty" style="display:none;">
        No pricing requests found.
      </p>
    </div>

    <style>
      table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
      }
      
      th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #e2e8f0;
      }
      
      th {
        background-color: #f8fafc;
        font-weight: 600;
        color: #374151;
      }
      
      .status-badge {
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
      }
      
      .status-approved {
        background-color: #dcfce7;
        color: #166534;
      }
      
      .status-pending {
        background-color: #fef3c7;
        color: #92400e;
      }
      
      .btn-approve {
        background-color: #10b981;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        margin-right: 8px;
      }
      
      .btn-approve:hover {
        background-color: #059669;
      }
      
      .btn-approve:disabled {
        background-color: #9ca3af;
        cursor: not-allowed;
      }
    </style>
  `;
}

function getDashboardView() {
  return `
    <div class="card">
      <h3>Admin Dashboard Overview</h3>
      <div id="statsContainer">
        <p>Loading dashboard statistics...</p>
      </div>
    </div>
  `;
}

function loadDashboardStats() {
  const container = document.getElementById("statsContainer");
  if (!container) return;

  apiRequest("/admin/stats/dashboard")
    .then((res) => {
      if (!res.ok) {
        container.innerHTML =
          '<p style="color: red;">Failed to load statistics</p>';
        return;
      }

      const stats = res.data;
      container.innerHTML = `
        <div class="stats-grid">
          <!-- User Statistics -->
          <div class="stat-card">
            <h4>👥 Users</h4>
            <div class="stat-row">
              <span class="stat-label">Total Users:</span>
              <span class="stat-value">${stats.users.total}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Students:</span>
              <span class="stat-value">${stats.users.students}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Experts:</span>
              <span class="stat-value">${stats.experts.approved}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Admins:</span>
              <span class="stat-value">${stats.users.admins}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">New This Week:</span>
              <span class="stat-value recent">${stats.users.recent_registrations}</span>
            </div>
          </div>

          <!-- Question Statistics -->
          <div class="stat-card">
            <h4>📝 Questions</h4>
            <div class="stat-row">
              <span class="stat-label">Total Questions:</span>
              <span class="stat-value">${stats.questions.total}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Pending:</span>
              <span class="stat-value pending">${stats.questions.pending}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Assigned:</span>
              <span class="stat-value">${stats.questions.assigned}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">In Negotiation:</span>
              <span class="stat-value negotiation">${stats.questions.in_negotiation}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">New This Week:</span>
              <span class="stat-value recent">${stats.questions.recent}</span>
            </div>
          </div>

          <!-- Order Statistics -->
          <div class="stat-card">
            <h4>📦 Orders</h4>
            <div class="stat-row">
              <span class="stat-label">Total Orders:</span>
              <span class="stat-value">${stats.orders.total}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Active:</span>
              <span class="stat-value active">${stats.orders.active}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Completed:</span>
              <span class="stat-value completed">${stats.orders.completed}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">New This Week:</span>
              <span class="stat-value recent">${stats.orders.recent}</span>
            </div>
          </div>

          <!-- Expert Approval Statistics -->
          <div class="stat-card">
            <h4>✅ Expert Approvals</h4>
            <div class="stat-row">
              <span class="stat-label">Pending Approval:</span>
              <span class="stat-value pending">${stats.experts.pending_approval}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Approved:</span>
              <span class="stat-value approved">${stats.experts.approved}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Approval Rate:</span>
              <span class="stat-value">${stats.experts.approval_rate}%</span>
            </div>
          </div>
        </div>

        <style>
          .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
          }
          
          .stat-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
          }
          
          .stat-card h4 {
            margin: 0 0 15px 0;
            font-size: 16px;
            color: #1e293b;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
          }
          
          .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f1f5f9;
          }
          
          .stat-row:last-child {
            border-bottom: none;
          }
          
          .stat-label {
            font-size: 14px;
            color: #64748b;
            font-weight: 500;
          }
          
          .stat-value {
            font-size: 14px;
            font-weight: 600;
            color: #1e293b;
          }
          
          .stat-value.pending {
            color: #f59e0b;
          }
          
          .stat-value.negotiation {
            color: #8b5cf6;
          }
          
          .stat-value.active {
            color: #3b82f6;
          }
          
          .stat-value.completed {
            color: #10b981;
          }
          
          .stat-value.approved {
            color: #10b981;
          }
          
          .stat-value.recent {
            color: #06b6d4;
          }
        </style>
      `;
    })
    .catch((error) => {
      console.error("Error loading dashboard stats:", error);
      container.innerHTML =
        '<p style="color: red;">Error loading statistics</p>';
    });
}

function getCreateEmployeeAdminView() {
  return `
    <div class="card">
      <h3>Create Employee (Admin)</h3>
      <p>Create a new employee admin account with system access.</p>
      
      <form id="createEmployeeForm" onsubmit="handleCreateEmployee(event)">
        <div class="form-group">
          <label for="employeeName">Full Name</label>
          <input type="text" id="employeeName" name="name" required placeholder="Enter employee full name">
        </div>
        
        <div class="form-group">
          <label for="employeeEmail">Email Address</label>
          <input type="email" id="employeeEmail" name="email" required placeholder="Enter email address">
        </div>
        
        <div class="form-group">
          <label for="employeePassword">Password</label>
          <input type="password" id="employeePassword" name="password" required placeholder="Enter password">
        </div>

        <div class="form-group">
          <label for="employeeMobileno">Mobile Number</label>
          <input type="text" id="employeeMobileno" name="mobileno" required placeholder="Enter mobile number">
        </div>
        
        <div class="error-message" id="employeeError"></div>
        <div class="success-message" id="employeeSuccess"></div>
        
        <div class="form-actions">
          <button type="submit" class="btn-primary">Create Employee</button>
          <button type="button" class="btn-secondary" onclick="resetEmployeeForm()">Reset</button>
        </div>
      </form>
    </div>
  `;
}

async function loadEmployeeDepartments() {
  const res = await apiRequest("/departments");
  if (!res.ok) {
    console.error(res.data?.error || "Failed to load departments");
    return;
  }
  const select = document.getElementById("employeeDepartment");
  if (!select) return;

  select.innerHTML = "";

  // Add default option
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Select Department";
  select.appendChild(defaultOption);

  // Add department options
  res.data.departments.forEach((dept) => {
    const option = document.createElement("option");
    option.value = dept.slug;
    option.textContent = dept.name;
    select.appendChild(option);
  });
}

async function handleCreateEmployee(event) {
  event.preventDefault();

  const form = document.getElementById("createEmployeeForm");
  const errorDiv = document.getElementById("employeeError");
  const successDiv = document.getElementById("employeeSuccess");

  // Hide previous messages
  errorDiv.style.display = "none";
  successDiv.style.display = "none";

  // Get form data
  const formData = new FormData(form);
  const data = {
    name: formData.get("name"),
    email: formData.get("email"),
    password: formData.get("password"),
    department: formData.get("department"),
    mobileno: formData.get("mobileno"),
  };

  try {
    const res = await apiRequest("/admin/employee-admin/create", "POST", data);

    if (!res.ok) {
      errorDiv.textContent = res.data.error || "Failed to create employee";
      errorDiv.style.display = "block";
      return;
    }

    // Success
    successDiv.textContent = "Employee created successfully!";
    successDiv.style.display = "block";

    // Reset form
    form.reset();

    // Optionally redirect or refresh after a delay
    setTimeout(() => {
      successDiv.style.display = "none";
    }, 3000);
  } catch (error) {
    errorDiv.textContent = "An unexpected error occurred";
    errorDiv.style.display = "block";
  }
}

function resetEmployeeForm() {
  const form = document.getElementById("createEmployeeForm");
  const errorDiv = document.getElementById("employeeError");
  const successDiv = document.getElementById("employeeSuccess");

  form.reset();
  errorDiv.style.display = "none";
  successDiv.style.display = "none";
}

// ----------------------------
// EXPERTS MANAGEMENT FUNCTIONS
// ----------------------------

function showExpertTab(tabName) {
  // Hide all tabs
  document.getElementById("pendingTab").style.display = "none";
  document.getElementById("allTab").style.display = "none";

  // Remove active class from all buttons
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.remove("active");
  });

  // Show selected tab and activate button
  if (tabName === "pending") {
    document.getElementById("pendingTab").style.display = "block";
    document.querySelector(".tab-btn:nth-child(1)").classList.add("active");
  } else if (tabName === "all") {
    document.getElementById("allTab").style.display = "block";
    document.querySelector(".tab-btn:nth-child(2)").classList.add("active");
  }
}

async function loadPendingExperts() {
  try {
    const res = await apiRequest("/admin/experts/pending");

    if (!res.ok) {
      console.error(res.data?.error || "Failed to load pending experts");
      return;
    }

    const tableBody = document.querySelector("#pendingExpertTable tbody");
    const emptyState = document.getElementById("pendingEmptyState");

    if (!tableBody) return;

    tableBody.innerHTML = "";

    if (!res.data.experts || res.data.experts.length === 0) {
      emptyState.style.display = "block";
      return;
    }

    emptyState.style.display = "none";

    res.data.experts.forEach((exp) => {
      const row = document.createElement("tr");

      row.innerHTML = `
        <td>${exp.name || "N/A"}</td>
        <td>${exp.email || "N/A"}</td>
        <td>${exp.department || "N/A"}</td>
        <td>
          <button class="btn-approve" onclick="approveExpert('${exp.expert_id}')">
            Approve
          </button>
        </td>
      `;

      tableBody.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading pending experts:", error);
  }
}

async function loadAllExperts() {
  try {
    const res = await apiRequest("/admin/experts/all");

    if (!res.ok) {
      console.error(res.data?.error || "Failed to load all experts");
      return;
    }

    const tableBody = document.querySelector("#allExpertTable tbody");
    const emptyState = document.getElementById("allEmptyState");

    if (!tableBody) return;

    tableBody.innerHTML = "";

    if (!res.data.experts || res.data.experts.length === 0) {
      emptyState.style.display = "block";
      return;
    }

    emptyState.style.display = "none";

    res.data.experts.forEach((exp) => {
      const row = document.createElement("tr");

      const statusClass = exp.approved ? "status-approved" : "status-pending";
      const statusText = exp.approved ? "Approved" : "Pending";

      row.innerHTML = `
        <td>${exp.name || "N/A"}</td>
        <td>${exp.email || "N/A"}</td>
        <td>${exp.department || "N/A"}</td>
        <td>${exp.mobile || "N/A"}</td>
        <td>
          <span class="status-badge ${statusClass}">${statusText}</span>
        </td>
        <td>
          <button class="btn-view" onclick="viewExpertDetails('${exp.expert_id}')">
            View Details
          </button>
        </td>
      `;

      tableBody.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading all experts:", error);
  }
}

async function approveExpert(expertId) {
  try {
    const res = await apiRequest(`/admin/experts/approve/${expertId}`, "POST");

    if (!res.ok) {
      alert(res.data?.error || "Failed to approve expert");
      return;
    }

    alert("Expert approved successfully!");

    // Refresh both tables
    loadPendingExperts();
    loadAllExperts();
  } catch (error) {
    console.error("Error approving expert:", error);
    alert("Failed to approve expert");
  }
}

function viewExpertDetails(expertId) {
  // This function can be expanded to show a modal with expert details
  alert(
    `Expert details for ID: ${expertId}\nThis feature can be expanded to show detailed expert information.`,
  );
}

async function loadPricingRequests() {
  try {
    const res = await apiRequest("/admin/employee-admin/pricing-requests");

    if (!res.ok) {
      console.error(res.data?.error || "Failed to load pricing requests");
      return;
    }

    const tableBody = document.querySelector("#pricingRequestsTable tbody");
    const emptyState = document.getElementById("pricingRequestsEmptyState");

    if (!tableBody) return;

    tableBody.innerHTML = "";

    if (!res.data || res.data.length === 0) {
      emptyState.style.display = "block";
      return;
    }

    emptyState.style.display = "none";

    res.data.forEach((req) => {
      const row = document.createElement("tr");

      const statusClass =
        req.status === "APPROVED" ? "status-approved" : "status-pending";
      const statusText = req.status === "APPROVED" ? "Approved" : "Pending";

      row.innerHTML = `
        <td>${req.questionId || "N/A"}</td>
        <td>$${req.studentPrice || "N/A"}</td>
        <td>$${req.expertPayout || "N/A"}</td>
        <td>
          <span class="status-badge ${statusClass}">${statusText}</span>
        </td>
        <td>
          ${
            req.status === "APPROVED"
              ? '<span class="approved-text">✓ Approved</span>'
              : `<button class="btn-approve" onclick="approvePricing('${req._id}')">Approve</button>`
          }
        </td>
      `;

      tableBody.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading pricing requests:", error);
  }
}

async function approvePricing(pricingId) {
  try {
    const res = await apiRequest(
      `/admin/employee-admin/approve/${pricingId}`,
      "POST",
    );

    if (!res.ok) {
      alert(res.data?.error || "Failed to approve pricing");
      return;
    }

    alert("Pricing approved successfully!");

    // Refresh the table
    loadPricingRequests();
  } catch (error) {
    console.error("Error approving pricing:", error);
    alert("Failed to approve pricing");
  }
}

async function loadStudents() {
  try {
    const res = await apiRequest("/admin/students/all");

    if (!res.ok) {
      console.error(res.data?.error || "Failed to load students");
      return;
    }

    const tableBody = document.querySelector("#studentsTable tbody");
    const emptyState = document.getElementById("studentsEmptyState");

    if (!tableBody) return;

    tableBody.innerHTML = "";

    if (!res.data || res.data.students.length === 0) {
      emptyState.style.display = "block";
      return;
    }

    emptyState.style.display = "none";

    res.data.students.forEach((student) => {
      const row = document.createElement("tr");

      const statusClass =
        student.status === "Active" ? "status-active" : "status-inactive";
      const createdDate = new Date(student.created_at).toLocaleDateString();

      row.innerHTML = `
        <td>${student.name || "N/A"}</td>
        <td>${student.email || "N/A"}</td>
        <td>
          <span class="status-badge ${statusClass}">${student.status}</span>
        </td>
        <td>${createdDate}</td>
      `;

      tableBody.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading students:", error);
  }
}

async function loadEmployeeAdmins() {
  try {
    const res = await apiRequest("/admin/students/employee-admins/all");

    if (!res.ok) {
      console.error(res.data?.error || "Failed to load employee admins");
      return;
    }

    const tableBody = document.querySelector("#employeeAdminsTable tbody");
    const emptyState = document.getElementById("employeeAdminsEmptyState");

    if (!tableBody) return;

    tableBody.innerHTML = "";

    if (!res.data || res.data.employee_admins.length === 0) {
      emptyState.style.display = "block";
      return;
    }

    emptyState.style.display = "none";

    res.data.employee_admins.forEach((admin) => {
      const row = document.createElement("tr");

      const statusClass =
        admin.status === "Active" ? "status-active" : "status-inactive";
      const createdDate = new Date(admin.created_at).toLocaleDateString();

      row.innerHTML = `
        <td>${admin.name || "N/A"}</td>
        <td>${admin.email || "N/A"}</td>
        <td>${admin.role || "N/A"}</td>
        <td>${admin.mobile || "N/A"}</td>
        <td>
          <span class="status-badge ${statusClass}">${admin.status}</span>
        </td>
        <td>${createdDate}</td>
      `;

      tableBody.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading employee admins:", error);
  }
}
