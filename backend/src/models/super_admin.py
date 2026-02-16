from datetime import datetime


class SuperAdmin:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.created_at = datetime.utcnow()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "created_at": self.created_at
        }
