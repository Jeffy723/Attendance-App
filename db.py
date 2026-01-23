from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in .env")

_client = None
_db = None


def get_db():
    """
    Returns MongoDB database instance.
    Database name is taken from the URI (attendanceDB).
    """
    global _client, _db

    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client.get_default_database()
        print(f"MongoDB connected → {_db.name}")

    return _db


def init_db():
    """
    MongoDB does not need table creation.
    This function ensures required collections exist
    by touching them once.
    """
    db = get_db()

    # Touch collections (auto-created on first insert)
    db.users
    db.semesters
    db.students
    db.subjects
    db.class_log
    db.attendance

    print("MongoDB collections initialized ✅")
