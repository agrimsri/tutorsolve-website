// ===============================
// STUDENT DASHBOARD DYNAMIC VIEWS
// ===============================

function loadStudentView(view) {
  const container = document.getElementById("studentContent");

  if (!container) return;

  switch (view) {
    case "dashboard":
      container.innerHTML = getStudentDashboardView();
      loadStudentDashboardData();
      break;

    case "ask-question":
      container.innerHTML = getAskQuestionView();
      loadDepartments();
      break;

    case "my-questions":
      container.innerHTML = getMyQuestionsView();
      loadStudentQuestions();
      break;

    case "my-orders":
      container.innerHTML = getMyOrdersView();
      loadMyOrders();
      break;

    case "global-feed":
      container.innerHTML = getGlobalFeedView();
      break;

    case "profile":
      container.innerHTML = getProfileView();
      loadStudentProfile();
      break;

    default:
      container.innerHTML = "<p>Page not found</p>";
  }
}

// ----------------------------
// VIEW TEMPLATES
// ----------------------------

function getStudentDashboardView() {
  return `
    <div class="card">
      <h3>Welcome to Student Dashboard</h3>
      <p>Track your questions, orders, and view global activity.</p>
    </div>

    <div class="card">
      <h3>Recent Activity</h3>
      <div id="recentActivity">
        <p>Loading recent activity...</p>
      </div>
    </div>

    <div class="card">
      <h3>Quick Stats</h3>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-number" id="totalQuestions">0</span>
          <span class="stat-label">Total Questions</span>
        </div>
        <div class="stat-item">
          <span class="stat-number" id="totalOrders">0</span>
          <span class="stat-label">Total Orders</span>
        </div>
      </div>
    </div>

    <style>
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 20px;
        margin-top: 20px;
      }
      
      .stat-item {
        text-align: center;
        padding: 20px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
      }
      
      .stat-number {
        display: block;
        font-size: 24px;
        font-weight: bold;
        color: #2563eb;
        margin-bottom: 5px;
      }
      
      .stat-label {
        font-size: 14px;
        color: #6b7280;
      }
    </style>
  `;
}

function getAskQuestionView() {
  return `
    <div class="card">
      <h3>Ask a New Question</h3>
      
      <input
        id="title"
        placeholder="Question title"
        style="width: 100%; margin-bottom: 10px"
      />

      <select id="department" style="width: 100%; margin-bottom: 10px">
        <option value="">Loading departments...</option>
      </select>

      <textarea
        id="description"
        placeholder="Describe your problem"
        style="width: 100%; height: 120px"
      ></textarea>

      <button onclick="submitStudentQuestion()" style="margin-top: 10px">
        Submit Question
      </button>
    </div>
  `;
}

function getMyQuestionsView() {
  return `
    <div class="card">
      <h3>My Questions</h3>
      <ul id="myQuestions" style="list-style: none; padding: 0">
        <li>Loading...</li>
      </ul>
    </div>
  `;
}

function getMyOrdersView() {
  return `
    <div class="card">
      <h3>My Orders</h3>
      <p class="empty">No active orders yet.</p>
    </div>
  `;
}

function getGlobalFeedView() {
  return `
    <div class="card">
      <h3>Global Feed</h3>
      <div class="feed-item">Physics Question #982 — Solved (A+)</div>
      <div class="feed-item">Java Assignment #134 — Completed</div>
      <div class="feed-item">Calculus Doubt #451 — Reviewed</div>
    </div>
  `;
}

function getProfileView() {
  return `
    <div class="card">
      <h3>Student Profile</h3>
      <div id="profileContent">
        <p>Loading profile...</p>
      </div>
    </div>
  `;
}

// ----------------------------
// LOAD FUNCTIONS
// ----------------------------

function loadStudentDashboardData() {
  // Load student stats and recent activity
  const token = localStorage.getItem("token");
  if (!token) return;

  // Placeholder data for now
  document.getElementById("totalQuestions").textContent = "0";
  document.getElementById("totalOrders").textContent = "0";
  document.getElementById("recentActivity").innerHTML = "<p>No recent activity</p>";
}

function loadStudentProfile() {
  const profileContent = document.getElementById("profileContent");
  if (!profileContent) return;
  
  profileContent.innerHTML = '<p>Loading profile...</p>';
  
  // Get profile data from /me endpoint
  apiRequest("/me").then(res => {
    if (!res.ok) {
      profileContent.innerHTML = '<p style="color: red;">Failed to load profile</p>';
      return;
    }
    
    const user = res.data;
    profileContent.innerHTML = `
      <div class="profile-section">
        <div class="profile-header">
          <div class="profile-avatar">
            ${user.picture ? `<img src="${user.picture}" alt="Profile" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover;">` : 
              '<div style="width: 80px; height: 80px; border-radius: 50%; background: #e5e7eb; display: flex; align-items: center; justify-content: center; font-size: 24px; color: #6b7280;">👤</div>'}
          </div>
          <div class="profile-info">
            <h4>${user.name || 'N/A'}</h4>
            <p style="color: #6b7280; margin: 5px 0;">Student Account</p>
          </div>
        </div>
        
        <div class="profile-details">
          <div class="detail-item">
            <label>Full Name:</label>
            <span>${user.name || 'N/A'}</span>
          </div>
          <div class="detail-item">
            <label>Email:</label>
            <span>${user.email || 'N/A'}</span>
          </div>
          <div class="detail-item">
            <label>Role:</label>
            <span>${user.role.join(', ')}</span>
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
      </style>
    `;
  }).catch(error => {
    console.error('Error loading profile:', error);
    profileContent.innerHTML = '<p style="color: red;">Error loading profile</p>';
  });
}

function loadMyOrders() {
  // Placeholder for orders loading
  const container = document.querySelector('#ordersContainer');
  if (container) {
    container.innerHTML = '<p class="empty">No active orders yet.</p>';
  }
}
