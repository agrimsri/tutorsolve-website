def register_routes(app):
    from src.routes.auth.routes import auth_bp
    from src.routes.admin.questions import admin_questions_bp
    from src.routes.questions.routes import questions_bp


    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_questions_bp)
    app.register_blueprint(questions_bp)