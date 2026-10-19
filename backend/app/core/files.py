"""업로드 파일 저장, 썸네일, 삭제. 공개 URL(/media/uploads/...)과 실제 경로를 변환한다."""
import io
import os
import uuid
from datetime import datetime
from typing import List, Union

from fastapi import UploadFile
from PIL import Image, ImageOps

from app.core.config import APP_DIR, LEGACY_UPLOAD_DIR, MERGED_DIR, UPLOAD_DIR

UPLOAD_URL_PREFIX = "/media/uploads/"

LEGACY_UPLOAD_URL_PREFIX = "/static/uploads/"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(MERGED_DIR, exist_ok=True)


def url_to_fs_path(url: str) -> str:
    """공개 URL을 실제 파일 경로로 바꾼다. 마이그레이션 전 URL(/static/uploads/...)도 처리한다."""
    if url.startswith(UPLOAD_URL_PREFIX):
        return str(UPLOAD_DIR / url[len(UPLOAD_URL_PREFIX):])
    if url.startswith(LEGACY_UPLOAD_URL_PREFIX):
        return str(LEGACY_UPLOAD_DIR / url[len(LEGACY_UPLOAD_URL_PREFIX):])
    return str(APP_DIR / url.lstrip("/"))


def upload_url(filename: str) -> str:
    return f"{UPLOAD_URL_PREFIX}{filename}"


def _to_rgb(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def save_upload(file: UploadFile, prefix: str) -> str:
    """업로드 파일을 저장하고 공개 URL을 반환한다. 이미지는 최대 1000px JPG로 줄여서 저장한다."""
    ensure_dirs()
    ext = os.path.splitext(file.filename or "")[1].lower()

    if ext == "":
        ext = ".bin"

    filename = f"{prefix}_{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, filename)

    raw = file.file.read()

    if ext in IMAGE_EXTS:
        try:
            img = _to_rgb(Image.open(io.BytesIO(raw)))
            img.thumbnail((1000, 1000))

            # jpg로 통일 저장
            filename = f"{prefix}_{uuid.uuid4().hex}.jpg"
            save_path = os.path.join(UPLOAD_DIR, filename)

            img.save(save_path, format="JPEG", quality=85, optimize=True)
            return upload_url(filename)
        except Exception:
            pass

    with open(save_path, "wb") as f:
        f.write(raw)

    return upload_url(filename)


def make_thumbnail_from_url(image_url: str | None, prefix: str = "thumb") -> str | None:
    if not image_url:
        return None

    src_path = url_to_fs_path(image_url)
    if not os.path.exists(src_path):
        return None

    try:
        with Image.open(src_path) as img:
            img = _to_rgb(img)
            img.thumbnail((360, 360))

            filename = f"{prefix}_{uuid.uuid4().hex}.jpg"
            save_path = os.path.join(UPLOAD_DIR, filename)
            img.save(save_path, format="JPEG", quality=82, optimize=True)

            return upload_url(filename)
    except Exception as e:
        print("THUMBNAIL ERROR:", e)
        return None


def try_remove_by_url(url: str | None):
    if not url:
        return
    path = url_to_fs_path(url)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def safe_download_filename(prefix: str, ext: str) -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{now}.{ext}"


def normalize_uploadfiles(
    files: Union[List[UploadFile], UploadFile, None]
) -> List[UploadFile]:
    """
    FastAPI에서 multipart 파일이
    - 여러개면 List[UploadFile]
    - 한개면 UploadFile
    - 없으면 None
    로 들어오는 경우가 있어서,
    항상 List[UploadFile]로 정규화해주는 함수.
    """
    if files is None:
        return []
    if isinstance(files, list):
        return files
    return [files]
