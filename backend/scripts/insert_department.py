import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ConfigurationError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def insert_departments():
    """Insert departments into MongoDB with error handling."""
    client = None
    try:
        load_dotenv()
        MONGO_URI = os.getenv("MONGO_URI")
        DB_NAME = os.getenv("MONGO_DB_NAME")
        if not MONGO_URI or not DB_NAME:
            raise RuntimeError("MONGO_URI or MONGO_DB_NAME not set")

        logger.info("Connecting to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        logger.info("MongoDB connection successful")

        db = client[DB_NAME]
        logger.info(f"Using database: {DB_NAME}")

        departments = [
            {"name": "Mechanical Engineering", "slug": "mechanical", "active": True},
            {"name": "Electronics", "slug": "electronics", "active": True},
            {"name": "Computer Science", "slug": "computer-science", "active": True},
            {"name": "Mathematics", "slug": "mathematics", "active": True},
        ]

        for dept in departments:
            result = db.departments.update_one(
                {"slug": dept["slug"]},
                {"$setOnInsert": dept},
                upsert=True
            )
            if result.upserted_id:
                logger.info(f"Inserted department: {dept['name']}")
            else:
                logger.info(f"Department already exists: {dept['name']}")

        logger.info("Departments seeded.")

    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failure: {e}")
        raise
    except ConfigurationError as e:
        logger.error(f"MongoDB configuration error: {e}")
        raise
    except OperationFailure as e:
        logger.error(f"MongoDB operation failure: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during department insertion: {e}")
        raise
    finally:
        if client:
            try:
                client.close()
                logger.info("MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")

if __name__ == "__main__":
    try:
        insert_departments()
    except Exception as e:
        logger.error(f"Script failed: {e}")
        exit(1)
