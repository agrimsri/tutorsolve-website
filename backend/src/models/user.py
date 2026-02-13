from enum import Enum

class UserRole(str, Enum):
    STUDENT = "student"
    EXPERT = "expert"
    EMPLOYEE = "employee"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    BANNED = "banned"
