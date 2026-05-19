import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent


def _database_path() -> Path:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        raw_path = database_url[5:] if database_url.startswith("file:") else database_url
        path = Path(raw_path)
        return path if path.is_absolute() else (Path.cwd() / path).resolve()
    return REPO_ROOT / "dev.db"


import secrets

DATABASE_PATH = _database_path()
JWT_SECRET = (
    os.getenv("JWT_SECRET")
    or os.getenv("SESSION_SECRET")
    or secrets.token_urlsafe(32)
)
COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8000")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(7 * 24 * 60 * 60)))
