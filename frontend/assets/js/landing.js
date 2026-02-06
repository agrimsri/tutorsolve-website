function handleGetSolution() {
  const input = document.getElementById("questionInput");
  const question = input.value.trim();

  if (!question) {
    alert("Please enter your question first.");
    return;
  }

  // Store question temporarily
  sessionStorage.setItem("pending_question", question);

  // Check if user is logged in (for now, very simple)
  const user = sessionStorage.getItem("user");

  if (user) {
    // User already logged in → go to student dashboard
    window.location.href = "../dashboards/student/index.html";
  } else {
    // Not logged in → redirect to signup
    window.location.href = "signup.html";
  }
}
