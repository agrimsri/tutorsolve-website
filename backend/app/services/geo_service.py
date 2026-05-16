import requests
from flask import request as flask_request
from app.utils.constants import BLOCKED_COUNTRIES

BYPASS_IPS = {"127.0.0.1", "::1", "localhost"}


def get_real_ip():
    """
    Returns the real client IP.
    Reads X-Forwarded-For first (set by Nginx/load-balancers),
    falls back to remote_addr.
    The X-Forwarded-For header may be a comma-separated list;
    the leftmost IP is the original client.
    """
    xff = flask_request.headers.get("X-Forwarded-For", "")
    if xff:
        # Take the first (leftmost) IP — that's the real client
        ip = xff.split(",")[0].strip()
        if ip:
            return ip
    return flask_request.remote_addr or ""


def get_country_from_ip(ip):
    # BYPASS_IPS check disabled for testing — re-enable in production:
    # if not ip or ip in BYPASS_IPS:
    #     return None
    try:
        resp = requests.get(f"https://ipapi.co/{ip}/country/", timeout=3)
        country = resp.text.strip().upper()
        return country if len(country) == 2 and country.isalpha() else None
    except Exception:
        return None


def is_blocked_country(ip):
    country = get_country_from_ip(ip)
    return country in BLOCKED_COUNTRIES if country else False
