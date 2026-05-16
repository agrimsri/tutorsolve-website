from app import celery
from app.extensions import get_db

@celery.task(name="app.tasks.diamond_tasks.broadcast_pending_questions")
def broadcast_pending_questions():
    """
    Every 5 minutes: find questions still in awaiting_quote status
    and notify approved experts in the matching domain.
    Only notifies each expert ONCE per question — tracks who has already
    been notified in the 'notified_expert_ids' field on the question document.
    """
    print("[CELERY] broadcast_pending_questions: START")
    db        = get_db()
    questions = list(db.questions.find({"status": "awaiting_quote"}))
    print(f"[CELERY] broadcast_pending_questions: Found {len(questions)} pending questions")

    for question in questions:
        domain  = question.get("domain")
        already_notified = set(str(x) for x in question.get("notified_expert_ids", []))

        experts = list(db.experts.find({
            "domain":     domain,
            "kyc_status": "approved",
        }))

        new_notified_ids = []

        for expert in experts:
            user_id    = str(expert["user_id"])
            expert_str = str(expert["_id"])

            # Skip if we already notified this expert about this question
            if expert_str in already_notified:
                continue

            print(f"[CELERY] Notifying expert user_id={user_id} about question={question['_id']}")
            from app.tasks.notification_tasks import send_notification_async
            try:
                send_notification_async.delay(
                    user_id,
                    "new_job_available",
                    "New Task in your Domain",
                    f"{question.get('title')}",
                    f"/expert/task-detail.html?id={str(question['_id'])}"
                )
                new_notified_ids.append(expert["_id"])
            except Exception as e:
                print(f"[CELERY][ERROR] dispatch FAILED for user_id={user_id}: {e}")

        # Persist the newly notified expert IDs so they aren't re-notified next cycle
        if new_notified_ids:
            db.questions.update_one(
                {"_id": question["_id"]},
                {"$addToSet": {"notified_expert_ids": {"$each": new_notified_ids}}}
            )

    print("[CELERY] broadcast_pending_questions: DONE")
