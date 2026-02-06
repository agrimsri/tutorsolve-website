function saveUserSession(user) {
  sessionStorage.setItem("user", JSON.stringify(user));
}

function getPendingQuestion() {
  return sessionStorage.getItem("pending_question");
}

function redirectAfterAuth(role) {
  if (role === "student") {
    window.location.href = "/dashboards/student/index.html";
  } else if (role === "expert") {
    window.location.href = "/dashboards/expert/index.html";
  }
}
