def register_routes(app):
    from src.routes.auth.auth import auth_bp

    app.register_blueprint(auth_bp)