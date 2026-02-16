from enum import Enum
from datetime import datetime


class EmployeeLevel(Enum):
    JUNIOR = "junior"
    SENIOR = "senior"


class Employee:
    def __init__(self, user_id: str, level: EmployeeLevel = EmployeeLevel.JUNIOR):
        self.user_id = user_id
        self.level = level
        self.created_at = datetime.utcnow()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "level": self.level.value,
            "created_at": self.created_at
        }
