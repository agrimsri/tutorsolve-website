async function studentSignup(name, email, password) {
  return apiRequest("/auth/signup/student", "POST", {
    name,
    email,
    password,
  });
}

async function expertSignup(name, email, password, department, mobileno) {
  return apiRequest("/auth/signup/expert", "POST", {
    name,
    email,
    password,
    department,
    mobileno,
  });
}

async function login(email, password) {
  return apiRequest("/auth/login", "POST", {
    email,
    password,
  });
}

async function adminSignup(name, email, password) {
  return apiRequest("/auth/signup/admin", "POST", {
    name,
    email,
    password,
  });
}
