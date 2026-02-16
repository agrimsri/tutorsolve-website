from datetime import datetime
from typing import Optional


class Student:
    def __init__(self, user_id: str, country: str, degree: Optional[str] = None):
        self.user_id = user_id
        self.country = country
        self.degree = degree
        self.total_orders = 0
        self.total_spent = 0.0
        self.created_at = datetime.utcnow()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "country": self.country,
            "degree": self.degree,
            "total_orders": self.total_orders,
            "total_spent": self.total_spent,
            "created_at": self.created_at
        }
