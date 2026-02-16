function saveUserSession(user) {
  localStorage.setItem("user", JSON.stringify(user));
  if (user.token) {
    localStorage.setItem("token", user.token);
  }
}

function getPendingQuestion() {
  return sessionStorage.getItem("pending_question");
}

function redirectAfterAuth(role) {
  if (role === "student") {
    window.location.href = "/dashboards/student/index.html";
  } else if (role === "expert") {
    window.location.href = "/dashboards/expert/index.html";
  } else if (role === "admin") {
    window.location.href = "/dashboards/admin/cockpit.html";
  } else if (role === "EmployeeAdmin") {
    window.location.href = "/dashboards/employee_admin/index.html";
  }
}
