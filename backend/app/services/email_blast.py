from app.extensions import get_db
from app.utils.constants import KYCStatus


def send_domain_blast(question):
    db = get_db()
    domain_id = question.get("domain_id")
    domain_name = question.get("domain")
    
    query = {"kyc_status": KYCStatus.APPROVED}
    if domain_id:
        query["$or"] = [
            {"domain_id": domain_id},
            {"domain": {"$regex": f"^{domain_name}$", "$options": "i"}}
        ]
    else:
        query["domain"] = {"$regex": f"^{domain_name}$", "$options": "i"}
        
    experts = list(db.experts.find(query))
    for expert in experts:
        user = db.users.find_one({"_id": expert["user_id"]})
        if not user or not user.get("email"):
            continue
        
        from app.services.email_service import send_expert_broadcast_email
        from app.tasks.notification_tasks import send_notification_async
        
        domain = domain_name or 'Assignment'
        send_expert_broadcast_email(user["email"], expert["name"], domain, question["title"], str(question["_id"]))
        
        send_notification_async.delay(
            user_id=str(user["_id"]),
            notif_type="expert_broadcast",
            title=f"New {domain} task",
            body=question["title"],
            link="/expert/job-board.html"
        )

