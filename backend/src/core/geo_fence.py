import requests
from flask import request, jsonify

# ISO country codes blocked for STUDENT access
BLOCKED_COUNTRIES = {"IN", "PK"}

# Simple in-memory cache to avoid repeated API calls
_ip_country_cache = {}


def get_client_ip():
    """
    Extract client IP considering proxies/load balancers.
    """
    if "X-Forwarded-For" in request.headers:
        # First IP is the real client
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    return request.remote_addr


def resolve_country(ip: str) -> str | None:
    """
    Resolve IP to country code using a public IP API.
    Cached for performance.
    """
    if ip in _ip_country_cache:
        return _ip_country_cache[ip]

    try:
        resp = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=2
        )
        if resp.status_code == 200:
            country = resp.json().get("country")
            _ip_country_cache[ip] = country
            return country
    except Exception:
        pass

    return None


def geo_fence_middleware():
    """
    Flask before_request middleware.
    Blocks student auth routes for users from IN/PK.
    """

    path = request.path

    # Only care about auth routes
    if not path.startswith("/auth"):
        return None

    client_ip = get_client_ip()
    country = resolve_country(client_ip)

    # If we can't resolve country, FAIL OPEN (important)
    if not country:
        return None

    # Block STUDENT signup explicitly
    if path == "/auth/signup/student" and country in BLOCKED_COUNTRIES:
        return jsonify({
            "error": "Student access not allowed from your country"
        }), 403

    # For login, we only block if intent is student
    if path == "/auth/login" and country in BLOCKED_COUNTRIES:
        data = request.get_json(silent=True) or {}
        if data.get("role") == "student":
            return jsonify({
                "error": "Student access not allowed from your country"
            }), 403

    return None
