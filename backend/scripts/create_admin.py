import os
import bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]

email = "agrimsri26@gmail.com"
password = "1234"

hashed_pw = bcrypt.hashpw(
    password.encode("utf-8"),
    bcrypt.gensalt()
).decode("utf-8")

db.users.insert_one({
    "name": "Agrim admin",
    "email": email,
    "password": hashed_pw,
    "role": ["Admin"],
    "isVerified": True,
    "createdAt": datetime.now(timezone.utc),
    "updatedAt": datetime.now(timezone.utc)
})

print("Admin created.")
