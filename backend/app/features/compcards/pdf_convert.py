"""LibreOffice(soffice)로 PPT/PPTX 컴카드의 첫 슬라이드 미리보기 PNG를 만든다."""
import os
import shutil
import subprocess
import uuid

from app.core.config import SOFFICE_PATH, UPLOAD_DIR
from app.core.files import upload_url, url_to_fs_path


def find_soffice() -> str | None:
    if SOFFICE_PATH and os.path.exists(SOFFICE_PATH):
        return SOFFICE_PATH
    p = shutil.which("soffice")
    if p:
        return p
    for c in ["/usr/bin/soffice", "/usr/local/bin/soffice"]:
        if os.path.exists(c):
            return c
    return None


def make_ppt_preview(ppt_public_url: str) -> str | None:
    """성공하면 미리보기 이미지의 공개 URL, 변환할 수 없으면 None."""
    ext = os.path.splitext(ppt_public_url)[1].lower()
    if ext not in [".ppt", ".pptx"]:
        return None

    ppt_path = url_to_fs_path(ppt_public_url)
    if not os.path.exists(ppt_path):
        return None

    soffice = find_soffice()
    if not soffice:
        return None

    out_dir = os.path.join(UPLOAD_DIR, f"ppt_preview_{uuid.uuid4().hex}")
    os.makedirs(out_dir, exist_ok=True)

    try:
        cmd = [
            soffice,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--nodefault",
            "--nofirststartwizard",
            "--convert-to",
            "png",
            "--outdir",
            os.path.abspath(out_dir),
            os.path.abspath(ppt_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        png_files = sorted([fn for fn in os.listdir(out_dir) if fn.lower().endswith(".png")])
        if not png_files:
            return None

        first_png_path = os.path.join(out_dir, png_files[0])

        preview_filename = f"compcard_preview_{uuid.uuid4().hex}.png"
        preview_save_path = os.path.join(UPLOAD_DIR, preview_filename)

        with open(first_png_path, "rb") as src, open(preview_save_path, "wb") as dst:
            dst.write(src.read())

        shutil.rmtree(out_dir, ignore_errors=True)
        return upload_url(preview_filename)

    except Exception as e:
        print("PPT PREVIEW ERROR:", e)
        shutil.rmtree(out_dir, ignore_errors=True)
        return None
