from datetime import datetime, timedelta
from app import celery
from app.extensions import get_db
from app.utils.helpers import oid
import redis
from config import Config
import logging

log = logging.getLogger(__name__)

_redis = redis.Redis.from_url(Config.REDIS_CACHE_URL, decode_responses=True)

@celery.task(name="app.tasks.notification_tasks.prune_old_notifications")
def prune_old_notifications():
    """
    Hourly cleanup:
    - Delete read notifications older than 7 days
    - Delete all notifications older than 30 days
    - Cap unread notifications per user at 50
    """
    db  = get_db()
    now = datetime.utcnow()

    r1 = db.notifications.delete_many({
        "is_read":    True,
        "created_at": {"$lt": now - timedelta(days=7)},
    })
    log.info(f"[NotifPrune] Deleted {r1.deleted_count} stale read notifications.")

    r2 = db.notifications.delete_many({
        "created_at": {"$lt": now - timedelta(days=30)},
    })
    log.info(f"[NotifPrune] Deleted {r2.deleted_count} ancient notifications.")

    # Per-user unread cap: delete oldest above 50
    pipeline = [
        {"$match":  {"is_read": False}},
        {"$group":  {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$match":  {"count": {"$gt": 50}}},
    ]
    pruned_unread = 0
    for bucket in db.notifications.aggregate(pipeline):
        user_oid = bucket["_id"]
        excess   = bucket["count"] - 50
        oldest   = list(
            db.notifications
              .find({"user_id": user_oid, "is_read": False})
              .sort("created_at", 1)
              .limit(excess)
        )
        ids = [d["_id"] for d in oldest]
        if ids:
            res = db.notifications.delete_many({"_id": {"$in": ids}})
            pruned_unread += res.deleted_count

    if pruned_unread:
        log.info(f"[NotifPrune] Pruned {pruned_unread} excess unread notifications.")

    return {"deleted": r1.deleted_count + r2.deleted_count + pruned_unread}


@celery.task(name="app.tasks.notification_tasks.send_notification_async")
def send_notification_async(user_id: str, notif_type: str, title: str, body: str, link: str = None):
    """
    Async wrapper so routes can fire-and-forget notifications without
    blocking the request cycle.
    """
    print(f"[CELERY] send_notification_async: START user_id={user_id} notif_type={notif_type}")
    try:
        from app.services.notification_service import create_notification
        create_notification(user_id, notif_type, title, body, link)
        print(f"[CELERY] send_notification_async: DONE user_id={user_id}")
    except Exception as e:
        print(f"[CELERY][ERROR] send_notification_async: FAILED for user_id={user_id}: {e}")
        raise


@celery.task(name="app.tasks.notification_tasks.notify_new_order_task")
def notify_new_order_task(question_id: str, title: str, domain_name: str):
    """
    Background task to notify all employees about a new order.
    """
    print(f"[CELERY] notify_new_order_task: START question_id={question_id} domain={domain_name}")
    db = get_db()
    from app.services.notification_service import create_notification
    
    try:
        employees = list(db.employees.find({}))
        print(f"[CELERY] notify_new_order_task: Notifying {len(employees)} employees")
        for emp in employees:
            print(f"[CELERY] notify_new_order_task: Sending to employee user_id={emp['user_id']}")
            create_notification(
                user_id_str=str(emp["user_id"]),
                notif_type="new_order_available",
                title="New Order Available",
                body=f"A new question in {domain_name} was posted: {title}",
                link=f"/admin/orders.html"
            )
        print(f"[CELERY] notify_new_order_task: DONE question_id={question_id}")
    except Exception as e:
        print(f"[CELERY][ERROR] notify_new_order_task: FAILED for question_id={question_id}: {e}")
        log.error(f"Failed to notify employees in background: {e}")

