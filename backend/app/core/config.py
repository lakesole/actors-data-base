"""환경변수 기반 설정. 다른 모듈은 경로와 키를 여기서만 가져온다."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent      # backend/app
PROJECT_ROOT = APP_DIR.parent.parent                   # 저장소 루트

load_dotenv(PROJECT_ROOT / ".env")

# 런타임 데이터(DB, 업로드 파일, 병합 PDF). git에 올리지 않고 도커 볼륨으로 연결한다.
STORAGE_DIR = Path(os.getenv("STORAGE_DIR") or PROJECT_ROOT / "storage")
DB_PATH = os.getenv("DB_PATH") or str(STORAGE_DIR / "actors.db")
UPLOAD_DIR = STORAGE_DIR / "uploads"     # /media/uploads/... 로 서빙
MERGED_DIR = STORAGE_DIR / "merged"      # 다운로드 응답으로만 내려보내고 서빙하지 않는다

# 마이그레이션 전 업로드 파일 위치 (/static/uploads/...). scripts/migrate_uploads_to_media.py로 옮긴다.
LEGACY_UPLOAD_DIR = Path(os.getenv("LEGACY_UPLOAD_DIR") or APP_DIR / "static" / "uploads")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("경고: SECRET_KEY 환경변수가 없어 임시 키를 사용합니다. 재시작하면 모든 로그인이 풀립니다.")

SESSION_COOKIE_NAME = "damactors_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7일
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"

# LibreOffice 실행 파일 경로. 비우면 PATH와 기본 위치에서 찾는다.
SOFFICE_PATH = os.getenv("SOFFICE_PATH", "")
