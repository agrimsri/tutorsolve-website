// ===============================
// STUDENT DASHBOARD DYNAMIC VIEWS
// ===============================
// Global variable to track current student view
let currentStudentView;

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

function loadStudentView(view) {
  const container = document.getElementById("studentContent");
  stopAllChatActivity();
  currentStudentView = view;

  if (!container) return;

  // Clear any running chat intervals when switching views
  clearChatIntervals();
  cleanupChatListeners();

  switch (view) {
    case "dashboard":
      container.innerHTML = getStudentDashboardView();
      loadStudentDashboardData();
      break;

    case "ask-question":
      container.innerHTML = getAskQuestionView();
      loadDepartments();
      // Handle pending question carry forward after the view is loaded
      handlePendingQuestionCarryForward();
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
    <div class="wrapper">
      <h1 class="dashboard-header">Dashboard</h1>

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
    </div>
  `;
}

function getAskQuestionView() {
  return `
    <div class="wrapper">
      <div>
        <h1 class="dashboard-header">Ask a New Question</h1>
        <p class="ask-subtext">
          Describe your problem clearly. Verified experts will review and quote.
        </p>
      </div>

      <form class="ask-form" onsubmit="submitStudentQuestion(event)">

        <div class="form-group">
          <label for="title">Question Title</label>
          <input
            type="text"
            id="title"
            name="title"
            placeholder="Enter a clear, concise title for your question"
            required
          />
        </div>

        <div class="form-group">
          <label for="department">Department</label>
          <select id="department" name="department" required>
            <option value="">Select a department...</option>
          </select>

        </div>

        <div class="form-group">
          <label for="description">Question Description</label>
          <textarea
            id="description"
            name="description"
            placeholder="Provide detailed information about your question. Include context, attempts, and specific help needed."
            required
          ></textarea>
        </div>

        <button type="submit" id="submitBtn">
          Submit Question
        </button>

      </form>
    </div>
     
  `;
}

function getMyQuestionsView() {
  return `
    <div class="card">
      <h3>My Questions</h3>
      <div id="myQuestionsContainer">
        <p>Loading questions...</p>
      </div>
    </div>
  `;
}

async function fetchMyQuestions() {
  return await apiRequest("/student/questions/mine", "GET");
}

function loadStudentQuestions() {
  const container = document.getElementById("myQuestionsContainer");
  if (!container) return;

  container.innerHTML = "<p>Loading questions...</p>";

  fetchMyQuestions()
    .then((res) => {
      if (!res.ok) {
        container.innerHTML =
          '<p style="color: red;">Failed to load questions</p>';
        return;
      }

      const questions = res.data.questions;
      console.log(questions);

      if (questions.length === 0) {
        container.innerHTML = '<p class="empty">No questions posted yet.</p>';
        return;
      }

      container.innerHTML = `
        <div class="questions-list">
          ${questions
            .map(
              (q) => `
            <div class="question-item">
              <div class="question-header">
                <h4>${q.title}</h4>
                <span class="status-badge ${q.status.toLowerCase()}">${q.status}</span>
              </div>
              <div class="question-details">
                <p><strong>Department:</strong> ${q.department || "N/A"}</p>
                <p><strong>Posted:</strong> ${new Date(q.createdAt).toLocaleDateString()}</p>
                <p><strong>Description:</strong> ${q.description.slice(0, 50)}...</p>
              </div>
              <div class="question-actions">
                <button onclick="openQuestionChat('${q.question_id}', '${q.title}')" class="chat-btn">
                  💬 Chat
                </button>
              </div>
              ${
                q.assignedExpert
                  ? `
                <div class="expert-info">
                  <p><strong>Assigned Expert:</strong> Expert ID: ${q.assignedExpert}</p>
                </div>
              `
                  : ""
              }
            </div>
          `,
            )
            .join("")}
        </div>

        <style>
          .questions-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-top: 16px;
          }
          
          .question-item {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 16px;
            background: #f9fafb;
          }
          
          .question-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
          }
          
          .question-header h4 {
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
          
          .status-badge.created {
            background: #fef3c7;
            color: #92400e;
          }
          
          .status-badge.assigned {
            background: #dbeafe;
            color: #1e40af;
          }
          
          .status-badge.negotiation {
            background: #e9d5ff;
            color: #7c3aed;
          }
          
          .question-details {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 12px;
          }
          
          .question-details p {
            margin: 0;
            font-size: 14px;
            color: #6b7280;
          }
          
          .question-details strong {
            color: #374151;
          }
          
          .question-actions {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #e5e7eb;
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
          
          .expert-info {
            padding-top: 12px;
            border-top: 1px solid #e5e7eb;
          }
          
          .expert-info p {
            margin: 0;
            font-size: 14px;
            color: #059669;
          }
        </style>
      `;
    })
    .catch((error) => {
      console.error("Error loading questions:", error);
      container.innerHTML =
        '<p style="color: red;">Error loading questions</p>';
    });
}

function getMyOrdersView() {
  return `
    <div class="card">
      <h3>My Orders</h3>
      <div id="myOrdersContainer">
        <p>Loading orders...</p>
      </div>
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

  // Check user authentication status
  checkUserAuth();

  // Placeholder data for now
  document.getElementById("totalQuestions").textContent = "0";
  document.getElementById("totalOrders").textContent = "0";
  document.getElementById("recentActivity").innerHTML =
    "<p>No recent activity</p>";
}

function checkUserAuth() {
  // Check current user authentication and role
  apiRequest("/me")
    .then((res) => {
      if (!res.ok) {
        console.error("Auth check failed:", res.data);
        return;
      }

      const user = res.data;
      console.log("Current user:", user);
      console.log("User role:", user.role);
      console.log("Is Student:", user.role.includes("Student"));

      if (!user.role.includes("Student")) {
        console.warn("User is not a Student! Role:", user.role);
      }
    })
    .catch((error) => {
      console.error("Error checking auth:", error);
    });
}

function loadStudentProfile() {
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
            <p style="color: #6b7280; margin: 5px 0;">Student Account</p>
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
    })
    .catch((error) => {
      console.error("Error loading profile:", error);
      profileContent.innerHTML =
        '<p style="color: red;">Error loading profile</p>';
    });
}

function loadMyOrders() {
  const container = document.getElementById("myOrdersContainer");
  if (!container) return;

  container.innerHTML = "<p>Loading orders...</p>";

  apiRequest("/student/orders")
    .then((res) => {
      if (!res.ok) {
        container.innerHTML =
          '<p style="color: red;">Failed to load orders</p>';
        return;
      }

      const orders = res.data.orders || [];

      if (orders.length === 0) {
        container.innerHTML = '<p class="empty">No active orders yet.</p>';
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
                <p><strong>Created:</strong> ${new Date(order.createdAt).toLocaleDateString()}</p>
                ${order.expert.name ? `<p><strong>Expert:</strong> ${order.expert.name}</p>` : ""}
                ${order.studentPrice ? `<p><strong>Price:</strong> $${order.studentPrice}</p>` : ""}
              </div>
              <div class="order-actions">
                ${
                  order.status === "NEGOTIATION"
                    ? `
                  <button onclick="openOrderChat('${order.order_id}', '${order.question.title}')" class="chat-btn">
                    💬 Chat with Expert
                  </button>
                `
                    : ""
                }
                ${
                  order.status === "ASSIGNED" || order.status === "IN_PROGRESS"
                    ? `
                  <button onclick="openOrderChat('${order.order_id}', '${order.question.title}')" class="chat-btn">
                    💬 View Chat
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
      console.error("Error loading orders:", error);
      container.innerHTML = '<p style="color: red;">Error loading orders</p>';
    });
}

// Enhanced form submission handler
function submitStudentQuestion(event) {
  event.preventDefault(); // Prevent form from submitting normally

  // Debug: Check authentication
  const token = localStorage.getItem("token");
  console.log("Token present:", !!token);
  console.log("Token value:", token);

  const form = event.target;
  const submitBtn = document.getElementById("submitBtn");
  const originalText = submitBtn.textContent;

  // Disable button and show loading state
  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting...";

  // Get form data
  const formData = new FormData(form);
  const questionData = {
    title: formData.get("title"),
    department: formData.get("department"),
    description: formData.get("description"),
  };

  console.log("Submitting question data:", questionData);

  // Call the existing submit function
  submitStudentQuestionData(questionData)
    .then(() => {
      // Reset form and show success
      form.reset();
      submitBtn.textContent = "✓ Submitted!";

      // Redirect to my questions after a delay
      setTimeout(() => {
        loadStudentView("my-questions");
      }, 1500);
    })
    .catch((error) => {
      console.error("Error submitting question:", error);
      submitBtn.textContent = "Error - Try Again";

      // Reset button after delay
      setTimeout(() => {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      }, 2000);
    });
}

// Separate function for the actual API call
async function submitStudentQuestionData(questionData) {
  try {
    const response = await apiRequest(
      "/student/questions/create",
      "POST",
      questionData,
    );

    if (!response.ok) {
      throw new Error(response.data?.error || "Failed to submit question");
    }

    return response.data;
  } catch (error) {
    throw error;
  }
}

// ===============================
// CHAT CLEANUP FUNCTIONS
// ===============================

function clearChatIntervals() {
  // Clear order chat interval
  if (window.chatInterval) {
    clearInterval(window.chatInterval);
    window.chatInterval = null;
  }

  // Clear question chat interval
  if (window.questionChatInterval) {
    clearInterval(window.questionChatInterval);
    window.questionChatInterval = null;
  }
}

function cleanupChatListeners() {
  // Remove event listeners for chat inputs
  const orderChatInput = document.getElementById("chatInput");
  const questionChatInput = document.getElementById("questionChatInput");

  if (orderChatInput) {
    orderChatInput.removeEventListener("keypress", null);
  }

  if (questionChatInput) {
    questionChatInput.removeEventListener("keypress", null);
  }
}

// ===============================
// CHAT FUNCTIONALITY
// ===============================

function openOrderChat(orderId, questionTitle) {
  const container = document.getElementById("studentContent");

  container.innerHTML = `
    <div class="card">
      <h3>Chat: ${questionTitle}</h3>
      <div id="chatContainer">
        <div class="chat-messages" id="chatMessages">
          <p>Loading messages...</p>
        </div>
        <div class="chat-input-container">
          <input type="text" id="chatInput" placeholder="Type your message..." />
          <button onclick="sendChatMessage('${orderId}')">Send</button>
        </div>
      </div>
      <button onclick="loadStudentView('my-orders')" class="back-btn">← Back to Orders</button>
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
      }
      
      .chat-message.student {
        background: #3b82f6;
        color: white;
        margin-left: auto;
      }
      
      .chat-message.expert {
        background: #e5e7eb;
        color: #111827;
      }
      
      .chat-message.admin {
        background: #fef3c7;
        color: #92400e;
        border: 1px solid #f59e0b;
      }
      
      .chat-message .sender {
        font-size: 12px;
        font-weight: bold;
        margin-bottom: 4px;
      }
      
      .chat-message .timestamp {
        font-size: 10px;
        opacity: 0.7;
        margin-top: 4px;
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
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
      }
      
      .chat-input-container button:hover {
        background: #2563eb;
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

  loadChatMessages(orderId);

  // Auto-refresh chat every 3 seconds
  if (window.chatInterval) clearInterval(window.chatInterval);
  window.chatInterval = setInterval(() => {
    if (currentStudentView !== "my-questions") {
      loadChatMessages(orderId);
    }
  }, 3000);

  // Add enter key support for chat input
  document
    .getElementById("chatInput")
    .addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        sendChatMessage(orderId);
      }
    });
}

async function loadChatMessages(orderId) {
  try {
    const messagesContainer = document.getElementById("chatMessages");
    if (!messagesContainer) return;

    // Detect if user is near bottom BEFORE updating
    const isNearBottom =
      messagesContainer.scrollHeight - messagesContainer.scrollTop <=
      messagesContainer.clientHeight + 50;

    const previousScrollHeight = messagesContainer.scrollHeight;
    const previousScrollTop = messagesContainer.scrollTop;

    const res = await apiRequest(`/student/orders/${orderId}/chat`);

    if (!res.ok) {
      console.error("Failed to load messages:", res.data);
      return;
    }

    const messages = res.data.messages || [];

    if (messages.length === 0) {
      messagesContainer.innerHTML =
        '<p style="color: #6b7280; text-align: center;">No messages yet. Start the conversation!</p>';
      return;
    }

    messagesContainer.innerHTML = messages
      .map((msg) => {
        const isStudent = msg.senderRole === "Student";
        const isAdmin = msg.senderRole === "EmployeeAdmin";
        const isExpert = msg.senderRole === "Expert";

        let senderName;
        if (isStudent) senderName = "You";
        else if (isAdmin) senderName = "Admin";
        else if (isExpert) senderName = "Expert";
        else senderName = "Unknown";

        const time = new Date(msg.createdAt).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        let messageClass = "expert";
        if (isStudent) messageClass = "student";
        else if (isAdmin) messageClass = "admin";
        else if (isExpert) messageClass = "expert";

        return `
          <div class="chat-message ${messageClass}">
            <div class="sender">${senderName}</div>
            <div class="message-text">${msg.message}</div>
            <div class="timestamp">${time}</div>
          </div>
        `;
      })
      .join("");

    // After render: handle scroll properly
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
    console.error("Error loading chat messages:", error);
  }
}

async function sendChatMessage(orderId) {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();

  if (!message) return;

  try {
    const res = await apiRequest(`/student/orders/${orderId}/chat`, "POST", {
      message,
    });

    if (!res.ok) {
      alert(res.data?.error || "Failed to send message");
      return;
    }

    // Clear input and refresh messages
    input.value = "";
    loadChatMessages(orderId);
  } catch (error) {
    console.error("Error sending message:", error);
    alert("Failed to send message");
  }
}

// ===============================
// QUESTION CHAT FUNCTIONALITY
// ===============================

function openQuestionChat(questionId, questionTitle) {
  const container = document.getElementById("studentContent");

  container.innerHTML = `
    <div class="card">
      <h3 style="margin-bottom:16px; font-weight:600; font-size:20px; color:#111827;">
        Chat: ${questionTitle}
      </h3>

      <div id="questionChatContainer">
        <div class="chat-messages" id="questionChatMessages">
          <p style="color:#6b7280;">Loading messages...</p>
        </div>

        <div class="chat-input-container">
          <input type="text" id="questionChatInput" placeholder="Type your message..." />
          <button onclick="sendQuestionChatMessage('${questionId}')">
            Send
          </button>
        </div>
      </div>

      <button onclick="loadStudentView('my-questions')" class="back-btn">
        ← Back to Questions
      </button>
    </div>

    <style>
      #questionChatContainer {
        display: flex;
        flex-direction: column;
        height: 520px;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        overflow: hidden;
        background: white;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
      }

      #questionChatMessages {
        flex: 1;
        padding: 20px;
        overflow-y: auto;
        background: #f8fafc;
        display: flex;
        flex-direction: column;
        gap: 12px;
        scroll-behavior: smooth;
      }

      /* Scrollbar styling */
      #questionChatMessages::-webkit-scrollbar {
        width: 6px;
      }

      #questionChatMessages::-webkit-scrollbar-thumb {
        background: #d1d5db;
        border-radius: 10px;
      }

      .chat-message {
        max-width: 75%;
        padding: 12px 14px;
        border-radius: 14px;
        font-size: 14px;
        line-height: 1.5;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        animation: fadeIn 0.2s ease-in-out;
      }

      .chat-message.student {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 4px;
      }

      .chat-message.admin {
        background: #fef3c7;
        color: #92400e;
        border: 1px solid #f59e0b;
        border-bottom-left-radius: 4px;
      }

      .chat-message.expert {
        background: #e5e7eb;
        color: #111827;
        border-bottom-left-radius: 4px;
      }

      .chat-message .sender {
        font-size: 11px;
        font-weight: 600;
        margin-bottom: 4px;
        opacity: 0.8;
        letter-spacing: 0.3px;
      }

      .chat-message .timestamp {
        font-size: 10px;
        opacity: 0.6;
        margin-top: 6px;
        text-align: right;
      }

      .chat-input-container {
        display: flex;
        padding: 16px;
        gap: 10px;
        background: white;
        border-top: 1px solid #e5e7eb;
      }

      .chat-input-container input {
        flex: 1;
        padding: 10px 14px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        font-size: 14px;
        transition: all 0.2s ease;
        outline: none;
      }

      .chat-input-container input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
      }

      .chat-input-container button {
        padding: 10px 18px;
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s ease;
      }

      .chat-input-container button:hover {
        background: #2563eb;
        transform: translateY(-1px);
      }

      .chat-input-container button:active {
        transform: translateY(0);
      }

      .back-btn {
        margin-top: 18px;
        padding: 10px 18px;
        background: #6b7280;
        color: white;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s ease;
      }

      .back-btn:hover {
        background: #4b5563;
        transform: translateY(-1px);
      }

      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(4px); }
        to { opacity: 1; transform: translateY(0); }
      }
    </style>
  `;

  loadQuestionChatMessages(questionId);

  if (window.questionChatInterval) clearInterval(window.questionChatInterval);
  window.questionChatInterval = setInterval(() => {
    loadQuestionChatMessages(questionId);
  }, 6000);

  document
    .getElementById("questionChatInput")
    .addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        sendQuestionChatMessage(questionId);
      }
    });
}

async function loadQuestionChatMessages(questionId) {
  try {
    const res = await apiRequest(`/student/questions/${questionId}/chat`);

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
        const isStudent = msg.senderRole === "Student";
        const isAdmin = msg.senderRole === "EmployeeAdmin";
        const isExpert = msg.senderRole === "Expert";

        let senderName;
        if (isStudent) senderName = "You";
        else if (isAdmin) senderName = "Admin";
        else if (isExpert) senderName = "Expert";
        else senderName = "Unknown";

        const time = new Date(msg.createdAt).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        let messageClass = "expert";
        if (isStudent) messageClass = "student";
        else if (isAdmin) messageClass = "admin";
        else if (isExpert) messageClass = "expert";

        return `
          <div class="chat-message ${messageClass}">
            <div class="sender">${senderName}</div>
            <div class="message-text">${msg.message}</div>
            <div class="timestamp">${time}</div>
          </div>
        `;
      })
      .join("");

    // ===== CONTROLLED SCROLL BEHAVIOR =====

    if (isNearBottom) {
      // Auto-scroll only if user was already near bottom
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    } else {
      // Preserve relative scroll position
      const newScrollHeight = messagesContainer.scrollHeight;
      messagesContainer.scrollTop =
        newScrollHeight - previousScrollHeight + previousScrollTop;
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
      `/student/questions/${questionId}/chat`,
      "POST",
      {
        message,
      },
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
// PAGE CLEANUP
// ===============================

// Clear intervals when user leaves the page
window.addEventListener("beforeunload", () => {
  clearChatIntervals();
});

// Clear intervals when page becomes hidden (tab switch, minimize, etc.)
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearChatIntervals();
  }
});
