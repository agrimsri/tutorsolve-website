from pymongo import MongoClient
from flask import current_app
import os


class Mongo:
    client: MongoClient = None
    db = None

    @classmethod
    def init_app(cls, app):
        uri = os.getenv("MONGO_URI")
        db_name = os.getenv("MONGO_DB_NAME")

        if not uri or not db_name:
            raise RuntimeError("MongoDB configuration missing")
        
        print(f"Connecting to MongoDB: {uri}")
        print(f"Database name: {db_name}")

        cls.client = MongoClient(uri)
        cls.db = cls.client[db_name]

        print("MongoDB connected successfully")

        # Attach to app for easy access
        app.mongo = cls.db
