from flask import Blueprint

student_bp = Blueprint("student", __name__)

from app.blueprints.student import routes  # noqa
