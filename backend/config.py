import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # MongoDB Atlas
    MONGO_URI     = os.environ.get("MONGO_URI")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "tutorsolve")

    # JWT
    JWT_SECRET_KEY          = os.environ.get("JWT_SECRET_KEY", "jwt-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 7  # 7 days in seconds

    # Stripe
    STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", STRIPE_PUBLIC_KEY)
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5001")
    API_BASE = os.environ.get("API_BASE", "http://localhost:5000/api")

    # Razorpay
    RAZORPAY_KEY_ID     = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

    # AWS S3
    AWS_ACCESS_KEY_ID     = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_BUCKET         = os.environ.get("AWS_S3_BUCKET", "tutorsolve-files")
    AWS_REGION            = os.environ.get("AWS_REGION", "us-east-1")

    # Mail
    # Switch between "sendgrid" and "smtp" by changing EMAIL_PROVIDER in .env
    EMAIL_PROVIDER  = os.environ.get("EMAIL_PROVIDER", "smtp").lower()
    MAIL_SERVER     = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT       = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS    = True
    MAIL_USERNAME   = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD   = os.environ.get("MAIL_PASSWORD", "")
    SENDGRID_API_KEY    = os.environ.get("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "support@tutorsolve.com")
    SENDGRID_FROM_NAME  = os.environ.get("SENDGRID_FROM_NAME", "TutorSolve")

    # Geo IP
    GEO_API_KEY = os.environ.get("GEO_API_KEY", "")

    # CORS — frontend origins allowed to call the API
    CORS_ORIGINS = ["*"] if os.environ.get("FLASK_ENV") == "development" else os.environ.get("CORS_ORIGINS", "http://localhost:5001").split(",")

    # --- Redis ---
    REDIS_SOCKETIO_URL = os.environ.get("REDIS_SOCKETIO_URL", "redis://localhost:6379/0")
    REDIS_CELERY_URL   = os.environ.get("REDIS_CELERY_URL",   "redis://localhost:6379/1")
    REDIS_CACHE_URL    = os.environ.get("REDIS_CACHE_URL",    "redis://localhost:6379/2")

    # --- Celery ---
    CELERY_BROKER_URL        = REDIS_CELERY_URL
    CELERY_RESULT_BACKEND    = REDIS_CACHE_URL
    CELERY_TASK_SERIALIZER   = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT    = ["json"]
    CELERY_TIMEZONE          = "UTC"
    CELERY_ENABLE_UTC        = True
