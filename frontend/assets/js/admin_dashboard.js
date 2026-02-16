function loadView(view) {
  const container = document.getElementById("adminContent");

  if (!container) return;

  switch (view) {
    case "experts":
      container.innerHTML = getExpertsView();
      loadPendingExperts();
      break;

    case "students":
      container.innerHTML = getStudentsView();
      break;

    case "dashboard":
      container.innerHTML = getDashboardView();
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
      <h3>Pending Expert Approvals</h3>

      <table id="expertTable">
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

      <p id="emptyState" class="empty" style="display:none;">
        No pending expert approvals.
      </p>
    </div>
  `;
}

function getStudentsView() {
  return `
    <div class="card">
      <h3>Students</h3>
      <p>Students module coming soon.</p>
    </div>
  `;
}

function getDashboardView() {
  return `
    <div class="card">
      <h3>Admin Dashboard Overview</h3>
      <p>System metrics and activity overview will appear here.</p>
    </div>
  `;
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
    const res = await apiRequest("/admin/employees-admin/create", "POST", data);

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
