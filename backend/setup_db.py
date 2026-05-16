"""
Database Setup and Seeding Script.
Creates MongoDB Atlas indexes and seeds initial data (Super Admin, Domains).

Run once before starting the app: python setup_db.py
Safe to re-run — PyMongo skips indexes that already exist, 
and seeding logic checks for existing records.
"""
import os
import sys
from datetime import datetime
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import get_db
from app.utils.constants import Role, DOMAINS

def setup_indexes(db):
    print("--- Creating Indexes ---")
    
    db.users.create_index("email", unique=True)
    print("users: email index")

    db.students.create_index("user_id", unique=True)
    print("students: user_id index")

    db.experts.create_index("user_id", unique=True)
    db.experts.create_index("domain")
    db.experts.create_index("kyc_status")
    print("experts: indexes")

    db.employees.create_index("user_id", unique=True)
    print("employees: user_id index")

    db.questions.create_index("student_id")
    db.questions.create_index("status")
    db.questions.create_index("domain")
    db.questions.create_index("assigned_expert_id")
    print("questions: indexes")

    db.threads.create_index("question_id")
    db.threads.create_index([("question_id", 1), ("thread_type", 1)])
    print("threads: indexes")

    db.messages.create_index([("thread_id", 1), ("created_at", 1)])
    print("messages: index")

    db.payments.create_index([("question_id", 1)], unique=True)
    db.payments.create_index([("completion_paid", 1), ("completion_paid_at", 1), ("payout_released", 1)])
    print("payments: index")

    db.payouts.create_index("expert_id")
    db.payouts.create_index("is_paid")
    print("payouts: indexes")

    db.files.create_index("question_id")
    print("files: index")

    db.feedback.create_index("question_id", unique=True)
    print("feedback: index")

    db.reviews.create_index("expert_id")
    db.reviews.create_index("question_id", unique=True)  # One review per order
    db.reviews.create_index("is_visible")
    print("reviews: indexes")

    db.notifications.create_index([("user_id", 1), ("is_read", 1)])
    db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    
    # TTL index: auto-delete read notifications 7 days after they were marked read
    db.notifications.create_index(
        "read_at",
        expireAfterSeconds=604800,  # 7 days
        sparse=True                 # only applies to docs that have read_at set
    )
    print("notifications: indexes")

def seed_data(db):
    print("\n--- Seeding Initial Data ---")
    
    # 1. Super Admin
    admin_email = os.environ.get("SUPER_ADMIN_EMAIL", "admin@tutorsolve.com")
    admin_password = os.environ.get("SUPER_ADMIN_PASSWORD", "Admin@123")
    
    existing_admin = db.users.find_one({"email": admin_email})
    if not existing_admin:
        db.users.insert_one({
            "email": admin_email,
            "password_hash": generate_password_hash(admin_password),
            "role": Role.SUPER_ADMIN,
            "is_active": True,
            "is_banned": False,
            "created_at": datetime.utcnow()
        })
        print(f"Created Super Admin: {admin_email}")
    else:
        print(f"Super Admin already exists: {admin_email}")

    # 2. Domains
    for domain_name in DOMAINS:
        existing_domain = db.domains.find_one({"name": domain_name})
        if not existing_domain:
            db.domains.insert_one({
                "name": domain_name,
                "is_active": True,
                "created_at": datetime.utcnow()
            })
            print(f"Created Domain: {domain_name}")
        else:
            # Silent skip or print if needed
            pass
    print("Domains seeding check complete.")

def main():
    app = create_app()
    with app.app_context():
        db = get_db()
        setup_indexes(db)
        seed_data(db)
        print("\nDatabase setup and seeding completed successfully.")

if __name__ == "__main__":
    main()
