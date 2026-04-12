"""TinyDB database setup and helpers."""
import os
from tinydb import TinyDB, Query
from config import DATABASE_PATH


def init_db():
    """Initialize database and ensure data directory exists."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    return TinyDB(DATABASE_PATH)


_db = None


def get_db():
    """Get or create database instance."""
    global _db
    if _db is None:
        _db = init_db()
    return _db


def get_tables():
    """Get all table references."""
    db = get_db()
    return {
        'categories': db.table('categories'),
        'products': db.table('products'),
        'sales': db.table('sales'),
        # ephemeral storage for POST→Redirect→GET prediction results
        'ai_pred_cache': db.table('ai_pred_cache'),
    }
