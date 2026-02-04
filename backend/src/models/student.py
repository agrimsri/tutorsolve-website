from datetime import datetime
from src.db.database import db


class Student(db.Model):
    __tablename__ = "students"

    user_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        primary_key=True
    )

    # Country is LOCKED after signup (enforced at service layer)
    country = db.Column(db.String(2), nullable=False)

    degree = db.Column(db.String(255))

    total_orders = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
