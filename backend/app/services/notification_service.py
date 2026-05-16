from datetime import datetime, timedelta
import redis
import json
import logging

from app.extensions import socketio, get_db
from app.utils.helpers import oid
from config import Config


# Redis client for the unread-count cache (DB 2)
def _get_redis():
    return redis.Redis.from_url(
        Config.REDIS_CACHE_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_keepalive=True,
    )

UNREAD_KEY  = "notif:user:{uid}:unread"
RECENT_KEY  = "notif:user:{uid}:recent"
RECENT_MAX  = 20
TTL_SECONDS = 86400  # 24 hours


def create_notification(user_id_str: str, notif_type: str, title: str, body: str, link: str = None):
    """
    Persist a notification to MongoDB, update Redis cache, and push
    a real-time event to the user's personal SocketIO room.

    This is safe to call from both Flask routes AND Celery tasks because
    socketio.emit() publishes to the Redis message_queue, not directly to
    a socket — the Gunicorn process delivers it to the connected client.
    """
    db     = get_db()
    uid    = str(user_id_str)
    now    = datetime.utcnow()

    # 1. Persist to MongoDB
    doc = {
        "user_id":    oid(uid),
        "type":       notif_type,
        "title":      title,
        "body":       body,
        "link":       link,
        "is_read":    False,
        "created_at": now,
    }
    print(f"[DEBUG] create_notification: Persisting to MongoDB for user {uid}")
    try:
        result = db.notifications.insert_one(doc)
        notif_id = str(result.inserted_id)
        print(f"[DEBUG] create_notification: Persisted to MongoDB, id {notif_id}")
    except Exception as e:
        print(f"[ERROR] create_notification: MongoDB insert failed: {e}")
        raise

    # 2. Update Redis cache (atomic pipeline)
    notification_dict = {
        "_id":        notif_id,
        "type":       notif_type,
        "title":      title,
        "body":       body,
        "link":       link,
        "is_read":    False,
        "created_at": now.isoformat(),
    }
    summary = json.dumps(notification_dict)
    
    print(f"[DEBUG] create_notification: Updating Redis cache for user {uid}")
    try:
        pipe = _get_redis().pipeline()
        pipe.incr(UNREAD_KEY.format(uid=uid))
        pipe.expire(UNREAD_KEY.format(uid=uid), TTL_SECONDS)
        pipe.lpush(RECENT_KEY.format(uid=uid), summary)
        pipe.ltrim(RECENT_KEY.format(uid=uid), 0, RECENT_MAX - 1)
        pipe.expire(RECENT_KEY.format(uid=uid), TTL_SECONDS)
        pipe.execute()
        print(f"[DEBUG] create_notification: Updated Redis cache for user {uid}")
    except Exception as e:
        print(f"[ERROR] create_notification: Redis cache update failed: {e}")
        # Note: we continue even if redis fails because mongodb is primary

    # 3. Push real-time event directly — safe because create_notification() is
    # ONLY ever called from Celery worker tasks (a separate process).
    # socketio.emit() with message_queue → Redis PUBLISH → Flask PubSub subscriber
    # delivers to the connected client. There is no in-process greenlet conflict
    # because the Celery worker is a completely separate OS process.
    # 3. Push real-time event via Redis message_queue → delivered by Gunicorn worker
    print(f"[DEBUG] create_notification: Emitting new_notification to user_{uid}")
    try:
        socketio.emit(
            "new_notification",
            notification_dict,
            room=f"user_{uid}",
        )
        print(f"[DEBUG] create_notification: Emitted new_notification to user_{uid}")
    except Exception as e:
        logging.getLogger(__name__).warning("socketio.emit failed: %s", e)
        print(f"[ERROR] create_notification: socketio.emit failed: {e}")

    return notif_id


def get_unread_count(user_id_str: str) -> int:
    uid = str(user_id_str)
    try:
        val = _get_redis().get(UNREAD_KEY.format(uid=uid))
    except Exception as e:
        logging.getLogger(__name__).warning("Redis get failed: %s", e)
        val = None

    if val is not None:
        return int(val)
    # Cache miss — count from MongoDB
    db    = get_db()
    count = db.notifications.count_documents({"user_id": oid(uid), "is_read": False})
    
    try:
        _get_redis().setex(UNREAD_KEY.format(uid=uid), TTL_SECONDS, count)
    except Exception as e:
        pass
        
    return count


def get_recent_notifications(user_id_str: str):
    uid = str(user_id_str)
    key = RECENT_KEY.format(uid=uid)
    
    try:
        raw = _get_redis().lrange(key, 0, 19)
    except Exception as e:
        logging.getLogger(__name__).warning("Redis lrange failed: %s", e)
        raw = None

    if raw:
        return [json.loads(item) for item in raw]

    # Cache miss — read from MongoDB
    db  = get_db()
    age_cutoff = datetime.utcnow() - timedelta(days=30)

    unread_items = list(
        db.notifications.find({
            "user_id": oid(uid),
            "is_read": False,
            "created_at": {"$gte": age_cutoff}
        })
        .sort("created_at", -1)
        .limit(20)
    )

    read_items = list(
        db.notifications.find({
            "user_id": oid(uid),
            "is_read": True,
            "created_at": {"$gte": age_cutoff}
        })
        .sort("created_at", -1)
        .limit(10)
    )

    combined = sorted(
        unread_items + read_items,
        key=lambda n: n["created_at"],
        reverse=True
    )[:20]

    serialised = [{
        "_id":        str(n["_id"]),
        "type":       n["type"],
        "title":      n["title"],
        "body":       n["body"],
        "link":       n.get("link"),
        "is_read":    n["is_read"],
        "created_at": n["created_at"].isoformat()
    } for n in combined]

    # Warm cache
    try:
        pipe = _get_redis().pipeline()
        for item in reversed(serialised):
            pipe.lpush(key, json.dumps(item))
        pipe.ltrim(key, 0, 19)
        pipe.expire(key, TTL_SECONDS)
        pipe.execute()
    except Exception as e:
        pass

    return serialised


def mark_all_read(user_id_str: str):
    uid = str(user_id_str)
    db  = get_db()
    now = datetime.utcnow()
    
    db.notifications.update_many(
        {"user_id": oid(uid), "is_read": False},
        {"$set": {"is_read": True, "read_at": now}},
    )
    
    try:
        _get_redis().set(UNREAD_KEY.format(uid=uid), 0)
        _get_redis().delete(RECENT_KEY.format(uid=uid))
    except Exception as e:
        pass
