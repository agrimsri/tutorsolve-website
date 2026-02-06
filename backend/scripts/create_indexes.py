import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, ConfigurationError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_indexes():
    """Create MongoDB indexes with proper error handling."""
    client = None
    
    try:
        # Load environment variables from .env
        load_dotenv()
        
        MONGO_URI = os.getenv("MONGO_URI")
        DB_NAME = os.getenv("MONGO_DB_NAME")
        
        if not MONGO_URI or not DB_NAME:
            raise RuntimeError("MONGO_URI or MONGO_DB_NAME not set in environment variables")
        
        logger.info("Connecting to MongoDB using URI: " + MONGO_URI)
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Test the connection
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
        db = client[DB_NAME]
        logger.info(f"Using database: {DB_NAME}")
        
        # USERS collection indexes
        logger.info("Creating indexes for 'users' collection...")
        try:
            db.users.create_index("email", unique=True)
            logger.info("Created unique index on 'users.email'")
        except OperationFailure as e:
            if "duplicate key" in str(e):
                logger.warning("Duplicate email found - index creation may have failed due to existing duplicates")
            else:
                logger.error(f"Failed to create unique index on 'users.email': {e}")
                raise
        
        try:
            db.users.create_index("role")
            logger.info("Created index on 'users.role'")
        except OperationFailure as e:
            logger.error(f"Failed to create index on 'users.role': {e}")
            raise
        
        # STUDENTS collection indexes
        logger.info("Creating indexes for 'students' collection...")
        try:
            db.students.create_index("user_id")
            logger.info("Created index on 'students.user_id'")
        except OperationFailure as e:
            logger.error(f"Failed to create index on 'students.user_id': {e}")
            raise
        
        # EXPERTS collection indexes
        logger.info("Creating indexes for 'experts' collection...")
        try:
            db.experts.create_index("user_id")
            logger.info("Created index on 'experts.user_id'")
        except OperationFailure as e:
            logger.error(f"Failed to create index on 'experts.user_id': {e}")
            raise
        
        logger.info("All indexes created successfully!")
        
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    except ConfigurationError as e:
        logger.error(f"MongoDB configuration error: {e}")
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
