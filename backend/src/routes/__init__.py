def register_routes(app):
    from src.routes.auth.routes import auth_bp

    app.register_blueprint(auth_bp)