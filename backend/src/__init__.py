from flask import Flask, send_from_directory
from src.db.mongo import Mongo
from src.core.geo_fence import geo_fence_middleware
from dotenv import load_dotenv
from flask_cors import CORS
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
PUBLIC_DIR = os.path.join(FRONTEND_DIR, "public")
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")


load_dotenv()

def create_app():

    app = Flask(
        __name__,
        static_folder=ASSETS_DIR,
        static_url_path="/assets"
    )

    # Load config
    from src.core.config import Config
    app.config.from_object(Config)

    # Mongo init
    Mongo.init_app(app)

    # Register geo fence middleware
    # app.before_request(geo_fence_middleware)

    # Serve landing page
    @app.route("/")
    def landing():
        return send_from_directory(PUBLIC_DIR, "index.html")

    # Serve all HTML files from public and dashboards directories
    @app.route("/<path:filename>")
    def serve_html_files(filename):
        if filename.endswith('.html'):
            # Try public directory first
            public_path = os.path.join(PUBLIC_DIR, filename)
            if os.path.exists(public_path):
                return send_from_directory(PUBLIC_DIR, filename)
            
            # Try dashboards directory
            dashboard_path = os.path.join(BASE_DIR, "frontend", filename)
            if os.path.exists(dashboard_path):
                return send_from_directory(os.path.join(BASE_DIR, "frontend"), filename)
        
        # Let Flask handle other files (404 for non-existent files)
        return "Not Found", 404

    # Register blueprints
    from src.routes import register_routes
    register_routes(app)

    # Enable CORS
    CORS(app)

    return app