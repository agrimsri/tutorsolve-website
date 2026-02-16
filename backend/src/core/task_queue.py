from rq import Queue
from src.core.redis_client import get_redis_connection


def get_queue():
    redis_conn = get_redis_connection()
    return Queue("default", connection=redis_conn)