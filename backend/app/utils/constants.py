class Role:
    STUDENT     = "student"
    EXPERT      = "expert"
    EMPLOYEE    = "employee"
    SUPER_ADMIN = "super_admin"


class OrderStatus:
    AWAITING_QUOTE  = "awaiting_quote"
    PENDING_PAYMENT = "pending_payment"
    IN_PROGRESS     = "in_progress"
    REVIEWING       = "reviewing"
    COMPLETED       = "completed"
    REFUNDED        = "refunded"
    CANCELLED       = "cancelled"


class KYCStatus:
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PaymentStatus:
    PENDING           = "pending"
    ADVANCE_PAID      = "advance_paid"
    FULLY_PAID        = "fully_paid"
    REFUND_REQUESTED  = "refund_requested"
    REFUNDED          = "refunded"


BLOCKED_COUNTRIES = ["IN", "PK"]

DOMAINS = [
    "Mathematics", "Physics", "Chemistry", "Biology",
    "Computer Science", "Engineering", "Economics",
    "Statistics", "Literature", "History", "Law", "Other",
]
