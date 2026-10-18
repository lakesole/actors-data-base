"""환경변수 기반 설정. 다른 모듈은 경로와 키를 여기서만 가져온다."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent      # backend/app
PROJECT_ROOT = APP_DIR.parent.parent                   # 저장소 루트

load_dotenv(PROJECT_ROOT / ".env")

DB_PATH = os.getenv("DB_PATH") or str(PROJECT_ROOT / "storage" / "actors.db")

TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = Path(os.getenv("STATIC_DIR") or APP_DIR / "static")
UPLOAD_DIR = STATIC_DIR / "uploads"
MERGED_DIR = STATIC_DIR / "merged"

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("경고: SECRET_KEY 환경변수가 없어 임시 키를 사용합니다. 재시작하면 모든 로그인이 풀립니다.")

SESSION_COOKIE_NAME = "damactors_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7일
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
