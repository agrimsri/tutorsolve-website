from pymongo import MongoClient
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_socketio import SocketIO
import redis

client       = None
mongo_db     = None
redis_client = None
jwt          = JWTManager()
mail         = Mail()
socketio     = SocketIO()


def init_db(app):
    global client, mongo_db, redis_client
    print(f"[DEBUG] extensions.init_db: Initializing PyMongo MongoClient (before fork if in master!)")
    client       = MongoClient(app.config["MONGO_URI"], connect=False)
    mongo_db     = client[app.config["MONGO_DB_NAME"]]
    redis_client = redis.from_url(app.config["REDIS_CACHE_URL"], decode_responses=True)
    print(f"[DEBUG] extensions.init_db: PyMongo and Redis clients created")


def get_db():
    if client is None:
        print("[WARN] extensions.get_db: get_db called but client is None!")
    return mongo_db

def get_redis():
    return redis_client
