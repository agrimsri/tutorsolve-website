from datetime import datetime
from src.db.database import db


class SuperAdmin(db.Model):
    __tablename__ = "super_admins"

    user_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        primary_key=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
