from flask import Blueprint, jsonify
from src.core.decorators import auth_required
from src.services.admin_stats_service import (
    AdminStatsService,
    AdminStatsServiceError
)

admin_stats_bp = Blueprint(
    "admin_stats",
    __name__,
    url_prefix="/admin/stats"
)


@admin_stats_bp.route("/dashboard", methods=["GET"])
@auth_required(["Admin"])
def get_dashboard_stats():
    try:
        stats = AdminStatsService.get_dashboard_stats()
        return jsonify(stats)
    except AdminStatsServiceError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500
