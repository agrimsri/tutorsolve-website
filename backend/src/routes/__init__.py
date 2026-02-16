def register_routes(app):
    from src.routes.auth.routes import auth_bp
    from src.routes.admin.questions import admin_questions_bp
    from src.routes.questions.routes import questions_bp
    from src.routes.departments.routes import departments_bp
    from src.routes.admin.experts import admin_experts_bp
    from src.routes.auth.me import me_bp
    from src.routes.expert.questions import expert_questions_bp
    from src.routes.admin.employee_admin import admin_employees_bp
    from src.routes.employee_admin.questions import employee_questions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_questions_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(admin_experts_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(expert_questions_bp)
    app.register_blueprint(admin_employees_bp)
    app.register_blueprint(employee_questions_bp)