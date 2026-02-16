async function detectCountryAndApplyUX() {
  if (!FRONTEND_CONFIG.ENABLE_GEO_DETECTION) {
    console.warn("[GeoUX] Frontend geo-detection disabled (DEV MODE)");
    return;
  }

  try {
    const res = await fetch(FRONTEND_CONFIG.GEO_API_URL);
    const data = await res.json();

    const country = data.country;
    console.log("[GeoUX] Detected country:", country);

    if (FRONTEND_CONFIG.BLOCKED_STUDENT_COUNTRIES.includes(country)) {
      applyBlockedStudentUX(country);
    }
  } catch (err) {
    console.warn("[GeoUX] Geo detection failed, relying on backend only");
  }
}

function applyBlockedStudentUX(country) {
  // Hide student-only actions
  document.querySelectorAll(".student-only").forEach((el) => {
    el.style.display = "none";
  });

  // Show region notice if present
  const notice = document.getElementById("regionNotice");
  if (notice) {
    notice.style.display = "block";
    notice.innerText = `Student services are not available in your region (${country}). Redirecting to expert application...`;
  }

  // Auto-redirect to expert application page after 2 seconds
  setTimeout(() => {
    window.location.href = "/apply-expert.html";
  }, 2000);
}
