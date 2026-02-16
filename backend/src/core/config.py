import os
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)

class Config:
    JWT_SECRET = os.getenv('JWT_SECRET', 'dev_secret_change_me')
    # Add other config variables as needed
