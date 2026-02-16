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


def create_indexes():
    """Create MongoDB indexes with proper error handling."""
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

        # ===============================
        # USERS
        # ===============================
        logger.info("Creating indexes for 'users' collection...")

        db.users.create_index("email", unique=True)
        db.users.create_index("role")

        logger.info("Users indexes created")

        # ===============================
        # EXPERTS (client schema)
        # ===============================
        logger.info("Creating indexes for 'experts' collection...")

        db.experts.create_index("user")
        db.experts.create_index("department")
        db.experts.create_index(
            [("department", 1), ("approve", 1)]
        )
        db.experts.create_index("user")
        db.experts.create_index("department")
        db.experts.create_index(
            [("department", 1), ("approve", 1)]
        )
        # ===============================
        logger.info("Creating indexes for 'departments' collection...")

        db.departments.create_index("slug", unique=True)
        db.departments.create_index("active")

        logger.info("Departments indexes created")

        # ===============================
        # QUESTIONS (Module 3)
        # ===============================
        logger.info("Creating indexes for 'questions' collection...")

        db.questions.create_index("user")
        db.questions.create_index("department")
        db.questions.create_index("status")

        # compound indexes for workflow
        db.questions.create_index(
            [("department", 1), ("status", 1)]
        )

        db.questions.create_index(
            [("user", 1), ("createdAt", -1)]
        )

        logger.info("Questions indexes created")

        logger.info("All indexes created successfully!")

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
        logger.error(f"Unexpected error during index creation: {e}")
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
        create_indexes()
    except Exception as e:
        logger.error(f"Script failed: {e}")
        exit(1)
