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
      <div id="assignedTasksContainer">
        <p>Loading assigned tasks...</p>
      </div>
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
  const container = document.getElementById("assignedTasksContainer");
  if (!container) return;

  container.innerHTML = "<p>Loading assigned tasks...</p>";

  apiRequest("/expert/orders")
    .then((res) => {
      if (!res.ok) {
        container.innerHTML =
          '<p style="color: red;">Failed to load assigned tasks</p>';
        return;
      }

      const orders = res.data.orders || [];

      if (orders.length === 0) {
        container.innerHTML = '<p class="empty">No tasks assigned yet.</p>';
        return;
      }

      container.innerHTML = `
        <div class="orders-list">
          ${orders
            .map(
              (order) => `
            <div class="order-item">
              <div class="order-header">
                <h4>${order.question.title}</h4>
                <span class="status-badge ${order.status.toLowerCase()}">${order.status}</span>
              </div>
              <div class="order-details">
                <p><strong>Department:</strong> ${order.question.department}</p>
                <p><strong>Student:</strong> ${order.student.name || "N/A"}</p>
                <p><strong>Created:</strong> ${new Date(order.createdAt).toLocaleDateString()}</p>
                ${order.expertPayout ? `<p><strong>Payout:</strong> $${order.expertPayout}</p>` : ""}
              </div>
              <div class="order-actions">
                ${
                  order.status === "NEGOTIATION" ||
                  order.status === "ASSIGNED" ||
                  order.status === "IN_PROGRESS"
                    ? `
                  <button onclick="openExpertOrderChat('${order.order_id}', '${order.question.title}')" class="chat-btn">
                    💬 Chat with Student
                  </button>
                `
                    : ""
                }
              </div>
            </div>
          `,
            )
            .join("")}
        </div>

        <style>
          .orders-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-top: 16px;
          }
          
          .order-item {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 16px;
            background: #f9fafb;
          }
          
          .order-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
          }
          
          .order-header h4 {
            margin: 0;
            color: #111827;
            font-size: 16px;
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
          
          .status-badge.assigned {
            background: #dbeafe;
            color: #1e40af;
          }
          
          .status-badge.in_progress {
            background: #fef3c7;
            color: #92400e;
          }
          
          .order-details {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 12px;
          }
          
          .order-details p {
            margin: 0;
            font-size: 14px;
            color: #6b7280;
          }
          
          .order-details strong {
            color: #374151;
          }
          
          .order-actions {
            display: flex;
            gap: 8px;
          }
          
          .chat-btn {
            background: #10b981;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.2s ease;
          }
          
          .chat-btn:hover {
            background: #059669;
          }
        </style>
      `;
    })
    .catch((error) => {
      console.error("Error loading assigned tasks:", error);
      container.innerHTML =
        '<p style="color: red;">Error loading assigned tasks</p>';
    });
}

function loadEarnings() {
  // Placeholder for earnings loading
  const earningsElement = document.querySelector(".earnings");
  if (earningsElement) {
    earningsElement.textContent = "₹0.00";
  }
}

// ===============================
// EXPERT CHAT FUNCTIONALITY
// ===============================

function openExpertOrderChat(orderId, questionTitle) {
  const container = document.getElementById("expertContent");

  container.innerHTML = `
    <div class="card">
      <h3>Chat: ${questionTitle}</h3>
      <div id="chatContainer">
        <div class="chat-messages" id="chatMessages">
          <p>Loading messages...</p>
        </div>
        <div class="chat-input-container">
          <input type="text" id="chatInput" placeholder="Type your message..." />
          <button onclick="sendExpertChatMessage('${orderId}')">Send</button>
        </div>
      </div>
      <button onclick="loadExpertView('assigned-tasks')" class="back-btn">← Back to Tasks</button>
    </div>

    <style>
      #chatContainer {
        display: flex;
        flex-direction: column;
        height: 500px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        overflow: hidden;
      }
      
      .chat-messages {
        flex: 1;
        padding: 16px;
        overflow-y: auto;
        background: #f9fafb;
        border-bottom: 1px solid #e5e7eb;
      }
      
      .chat-message {
        margin-bottom: 12px;
        padding: 8px 12px;
        border-radius: 8px;
        max-width: 80%;
        word-wrap: break-word;
      }
      
      .chat-message.expert {
        background: #10b981;
        color: white;
        margin-left: auto;
        text-align: right;
      }
      
      .chat-message.student {
        background: #3b82f6;
        color: white;
        margin-right: auto;
      }
      
      .chat-message.admin {
        background: #f59e0b;
        color: white;
        margin-left: auto;
        text-align: right;
      }
      
      .chat-message .sender {
        font-size: 12px;
        font-weight: bold;
        margin-bottom: 4px;
        opacity: 0.9;
      }
      
      .chat-message .message-text {
        margin-bottom: 4px;
        line-height: 1.4;
      }
      
      .chat-message .timestamp {
        font-size: 10px;
        opacity: 0.7;
      }
      
      .chat-input-container {
        display: flex;
        padding: 16px;
        gap: 8px;
        background: white;
      }
      
      .chat-input-container input {
        flex: 1;
        padding: 8px 12px;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        font-size: 14px;
      }
      
      .chat-input-container button {
        padding: 8px 16px;
        background: #10b981;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
      }
      
      .chat-input-container button:hover {
        background: #059669;
      }
      
      .back-btn {
        margin-top: 16px;
        padding: 8px 16px;
        background: #6b7280;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
      }
      
      .back-btn:hover {
        background: #4b5563;
      }
    </style>
  `;

  loadExpertChatMessages(orderId);

  // Auto-refresh chat every 3 seconds
  if (window.expertChatInterval) clearInterval(window.expertChatInterval);
  window.expertChatInterval = setInterval(() => {
    loadExpertChatMessages(orderId);
  }, 3000);

  // Add enter key support for chat input
  document
    .getElementById("chatInput")
    .addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        sendExpertChatMessage(orderId);
      }
    });
}

async function loadExpertChatMessages(orderId) {
  try {
    const res = await apiRequest(`/expert/orders/${orderId}/chat`);

    if (!res.ok) {
      console.error("Failed to load chat messages:", res.data);
      return;
    }

    const messages = res.data.messages || [];
    const messagesContainer = document.getElementById("chatMessages");

    if (!messagesContainer) return;

    if (messages.length === 0) {
      messagesContainer.innerHTML =
        '<p style="color: #6b7280; text-align: center;">No messages yet. Start the conversation!</p>';
      return;
    }

    messagesContainer.innerHTML = messages
      .map((msg) => {
        const isExpert = msg.senderRole === "Expert";
        const isStudent = msg.senderRole === "Student";
        const isAdmin = msg.senderRole === "EmployeeAdmin";

        let senderName = "Unknown";
        let messageClass = "chat-message-other";

        if (isExpert) {
          senderName = "You";
          messageClass = "chat-message-expert";
        } else if (isStudent) {
          senderName = "Student";
          messageClass = "chat-message-student";
        } else if (isAdmin) {
          senderName = "Admin";
          messageClass = "chat-message-admin";
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

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  } catch (error) {
    console.error("Error loading chat messages:", error);
  }
}

async function sendExpertChatMessage(orderId) {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();

  if (!message) return;

  try {
    const res = await apiRequest(`/expert/orders/${orderId}/chat`, "POST", {
      message,
    });

    if (!res.ok) {
      alert(res.data?.error || "Failed to send message");
      return;
    }

    // Clear input and refresh messages
    input.value = "";
    loadExpertChatMessages(orderId);
  } catch (error) {
    console.error("Error sending message:", error);
    alert("Failed to send message");
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
                class="question-btn applied-btn">
          ✓ Applied
        </button>
      `;
    } else {
      buttonHTML = `
        <button onclick="expressInterest('${q.question_id}', this)" 
                class="question-btn apply-btn">
          🎯 I Want to Solve
        </button>
      `;
    }

    li.innerHTML = `
      <div class="question-card">
        <div class="question-header">
          <h4 class="question-title">${q.title}</h4>
          <span class="question-department">${q.department || "General"}</span>
        </div>
        <div class="question-description">
          ${q.description.slice(0, 100) + "..."}
        </div>
        <div class="question-footer">
          ${buttonHTML}
        </div>
      </div>
    `;

    list.appendChild(li);
  });

  // Add styles for the available questions section
  if (!document.getElementById("available-questions-styles")) {
    const style = document.createElement("style");
    style.id = "available-questions-styles";
    style.textContent = `
      #availableQuestions {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      
      .question-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }
      
      .question-card:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        transform: translateY(-2px);
      }
      
      .question-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
      }
      
      .question-title {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
        color: #111827;
        line-height: 1.4;
        flex: 1;
        margin-right: 12px;
      }
      
      .question-department {
        background: #f3f4f6;
        color: #6b7280;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        white-space: nowrap;
      }
      
      .question-description {
        color: #4b5563;
        font-size: 14px;
        line-height: 1.6;
        margin-bottom: 16px;
        padding: 12px;
        background: #f9fafb;
        border-radius: 8px;
        border-left: 4px solid #3b82f6;
      }
      
      .question-footer {
        display: flex;
        justify-content: flex-end;
      }
      
      .question-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      
      .apply-btn {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
      }
      
      .apply-btn:hover:not(:disabled) {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
      }
      
      .applied-btn {
        background: #10b981;
        color: white;
        cursor: not-allowed;
        opacity: 0.8;
      }
      
      .question-btn:disabled {
        transform: none;
        box-shadow: none;
      }
      
      /* Empty state styling */
      #availableQuestions li:only-child {
        text-align: center;
        padding: 40px 20px;
        color: #6b7280;
        font-style: italic;
        background: #f9fafb;
        border-radius: 12px;
        border: 2px dashed #e5e7eb;
      }
    `;
    document.head.appendChild(style);
  }
}

// ===============================
// EXPRESS INTEREST
// ===============================

async function expressInterest(questionId, btn) {
  btn.disabled = true;
  btn.innerText = "Applying...";
  btn.className = "question-btn applied-btn";

  const res = await apiRequest(
    `/expert/questions/interest/${questionId}`,
    "POST",
  );

  if (!res.ok) {
    btn.disabled = false;
    btn.innerText = "🎯 I Want to Solve";
    btn.className = "question-btn apply-btn";
    alert(res.data.error || "Failed to register interest");
    return;
  }

  // Update button immediately
  btn.innerText = "✓ Applied";
  btn.className = "question-btn applied-btn";
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
