from pymongo import MongoClient
import streamlit as st
from dotenv import load_dotenv
import os
import pickle

# Load environment variables
load_dotenv()

MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASS = os.getenv("MONGO_PASS")
MONGO_CLUSTER = os.getenv("MONGO_CLUSTER")
DB_NAME = os.getenv("MONGO_DB")

if not all([MONGO_USER, MONGO_PASS, MONGO_CLUSTER, DB_NAME]):
    raise ValueError("❌ Missing MongoDB environment variables. Please check your .env file.")

# Build connection string
MONGO_URI = f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_CLUSTER}/{DB_NAME}?retryWrites=true&w=majority"

CACHE_FILE = "data_cache.pkl"


@st.cache_resource
def get_database():
    """Create a cached connection to MongoDB Atlas"""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


def load_collections():
    """Load collections from cache or MongoDB"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass  # fallback to DB if cache is corrupted

    # ❌ No cache → fetch from DB
    db = get_database()
    data_collections = {}
    try:
        collections = db.list_collection_names()
        for col in collections:
            data_collections[col] = list(db[col].find({}))
        # Save to pickle for next run
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(data_collections, f)
    except Exception as e:
        st.error(f"⚠️ Could not load collections: {e}")

    return data_collections


# ✅ only load when the file is imported, not when it’s executed in a loop
data_collections = load_collections()
