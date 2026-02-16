const API_BASE = "http://localhost:5000";

async function apiRequest(endpoint, method = "GET", body = null) {
  const options = {
    method,
    headers: {
      "Content-Type": "application/json",
    },
  };

  // Add Authorization header if JWT token is present
  const token = localStorage.getItem("token");
  if (token) {
    options.headers["Authorization"] = `Bearer ${token}`;
  } else {
    const user = JSON.parse(localStorage.getItem("user") || "null");
    if (user && user.token) {
      options.headers["Authorization"] = `Bearer ${user.token}`;
    }
  }

  if (body) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, options);
  const data = await response.json();

  return {
    ok: response.ok,
    status: response.status,
    data,
  };
}
