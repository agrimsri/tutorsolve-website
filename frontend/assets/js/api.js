const API_BASE = "http://localhost:5000";

async function apiRequest(endpoint, method = "GET", body = null) {
  console.log(
    "Token in apiRequest:",
    JSON.parse(sessionStorage.getItem("token") || "null"),
  );
  const options = {
    method,
    headers: {
      "Content-Type": "application/json",
    },
  };

  // Add Authorization header if JWT token is present
  const user = JSON.parse(sessionStorage.getItem("user") || "null");
  console.log("[apiRequest] sessionStorage user:", user);
  if (user && user.token) {
    console.log("[apiRequest] Using token:", user.token);
    options.headers["Authorization"] = `Bearer ${user.token}`;
  } else {
    console.log("[apiRequest] No token found in sessionStorage");
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
