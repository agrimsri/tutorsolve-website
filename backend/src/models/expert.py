from enum import Enum
from datetime import datetime
from src.db.database import db


class KYCStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Expert(db.Model):
    __tablename__ = "experts"

    user_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        primary_key=True
    )

    domain = db.Column(db.String(100), nullable=False)

    kyc_status = db.Column(
        db.Enum(KYCStatus),
        nullable=False,
        default=KYCStatus.PENDING
    )

    quality_score = db.Column(db.Float, default=0.0)
    on_time_rate = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
