"""Application configuration."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'sales_db.json')
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Admin login (use env vars in production)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Optional external AI prediction API (if set, /reports/ai-prediction will call it)
AI_PREDICTION_API_URL = os.environ.get('AI_PREDICTION_API_URL', '').strip()
AI_PREDICTION_API_KEY = os.environ.get('AI_PREDICTION_API_KEY', '').strip()
AI_PREDICTION_API_TIMEOUT_SECONDS = float(os.environ.get('AI_PREDICTION_API_TIMEOUT_SECONDS', '20') or 20)
