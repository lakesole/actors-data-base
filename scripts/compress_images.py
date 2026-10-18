import os
import sys
from pathlib import Path

# backend/app 설정(DB_PATH, 업로드 경로)을 그대로 쓴다
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from PIL import Image, ImageOps

from app.core.config import UPLOAD_DIR

MAX_SIZE = 1000
QUALITY = 85

def compress_image(path):
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)

            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")

            img.thumbnail((MAX_SIZE, MAX_SIZE))

            img.save(path, "JPEG", quality=QUALITY, optimize=True)

            print(f"완료: {path}")

    except Exception as e:
        print(f"실패: {path}")


def run():
    for root, dirs, files in os.walk(UPLOAD_DIR):
        for file in files:
            if file.lower().endswith(("jpg","jpeg","png","webp")):
                compress_image(os.path.join(root, file))


if __name__ == "__main__":
    run()