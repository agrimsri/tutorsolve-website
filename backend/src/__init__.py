from flask import Flask
from src.db.database import db


def create_app(config_object=None):
    app = Flask(__name__)

    # Temporary config (will be externalized later)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tutorsolve.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if config_object:
        app.config.from_object(config_object)

    # Initialize extensions
    db.init_app(app)

    # Register routes
    from src.routes import register_routes
    register_routes(app)

    with app.app_context():
        # Import models so SQLAlchemy registers them
        from src.models.user import User
        from src.models.student import Student
        from src.models.expert import Expert
        from src.models.employee import Employee
        from src.models.super_admin import SuperAdmin

        db.create_all()

    return app
