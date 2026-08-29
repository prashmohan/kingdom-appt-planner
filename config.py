import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-for-internal-use-only-123")
    SUPERADMIN_SECRET = os.environ.get(
        "SUPERADMIN_SECRET", "dev-superadmin-secret-change-me"
    )
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/planner.db")
    ENABLE_SCREENSHOT_UPLOAD = (
        os.environ.get("ENABLE_SCREENSHOT_UPLOAD", "false").lower() == "true"
    )
    GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID")
    EXTERNAL_API_SECRET = os.environ.get("EXTERNAL_API_SECRET", "mN4!pQs6JrYwV9")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB upload limit

    # Session cookie security defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )
