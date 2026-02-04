from enum import Enum
from datetime import datetime
from src.db.database import db

class EmployeeLevel(Enum):
    JUNIOR = "junior"
    SENIOR = "senior"


class Employee(db.Model):
    __tablename__ = "employees"

    user_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        primary_key=True
    )

    level = db.Column(
        db.Enum(EmployeeLevel),
        nullable=False,
        default=EmployeeLevel.JUNIOR
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
