import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-internal-use-only-123')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'data/planner.db')
    ENABLE_SCREENSHOT_UPLOAD = os.environ.get('ENABLE_SCREENSHOT_UPLOAD', 'false').lower() == 'true'
    EXTERNAL_API_SECRET = os.environ.get('EXTERNAL_API_SECRET', 'mN4!pQs6JrYwV9')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB upload limit

