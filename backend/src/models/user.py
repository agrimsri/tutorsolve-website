import uuid
from datetime import datetime
from enum import Enum
from src.db.database import db


class UserRole(Enum):
    STUDENT = "student"
    EXPERT = "expert"
    EMPLOYEE = "employee"
    SUPER_ADMIN = "super_admin"


class UserStatus(Enum):
    ACTIVE = "active"
    PENDING = "pending"
    BANNED = "banned"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.Enum(UserRole), nullable=False)
    status = db.Column(db.Enum(UserStatus), nullable=False, default=UserStatus.PENDING)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
