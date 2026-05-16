import json
from app.extensions import get_redis

CACHE_KEY_PREFIX = "chat:thread:"
MAX_CACHED       = 100
TTL_SECONDS      = 60 * 60 * 24  # 24 hours


def _key(thread_id):
    return f"{CACHE_KEY_PREFIX}{thread_id}"


def push_message(thread_id, message_dict):
    """
    Push a new message to the cache list.
    message_dict must be JSON-serialisable (no ObjectIds).
    Caps the list at MAX_CACHED and refreshes TTL.
    """
    r   = get_redis()
    key = _key(thread_id)
    r.rpush(key, json.dumps(message_dict))
    r.ltrim(key, -MAX_CACHED, -1)     # Keep only last 100
    r.expire(key, TTL_SECONDS)


def get_messages(thread_id):
    """
    Returns list of message dicts from cache, or None if cache is cold.
    """
    r      = get_redis()
    key    = _key(thread_id)
    raw    = r.lrange(key, 0, -1)
    if not raw:
        return None
    return [json.loads(item) for item in raw]


def warm_cache(thread_id, messages):
    """
    Populate cache from MongoDB results on a cache miss.
    Call this when get_messages() returns None.
    messages is a list of dicts (already serialised — no ObjectIds).
    """
    r   = get_redis()
    key = _key(thread_id)
    pipe = r.pipeline()
    pipe.delete(key)
    for msg in messages[-MAX_CACHED:]:
        pipe.rpush(key, json.dumps(msg))
    pipe.expire(key, TTL_SECONDS)
    pipe.execute()


def invalidate(thread_id):
    """Force cache eviction — use when you need to guarantee a cold read."""
    get_redis().delete(_key(thread_id))
