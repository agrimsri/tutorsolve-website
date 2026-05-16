from flask import Blueprint

expert_bp = Blueprint("expert", __name__)

from app.blueprints.expert import routes  # noqa
