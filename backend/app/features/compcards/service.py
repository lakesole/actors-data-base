import os

from app.core.files import IMAGE_EXTS
from app.features.compcards.pdf_convert import make_ppt_preview


def make_preview(compcard_url: str, original_filename: str) -> str | None:
    """
    업로드된 컴카드의 미리보기 URL.
    PDF와 이미지는 파일 자체, PPT는 첫 슬라이드 PNG, 그 외는 None.
    """
    ext = os.path.splitext(original_filename or "")[1].lower()
    if ext == ".pdf":
        return compcard_url
    if ext in [".ppt", ".pptx"]:
        return make_ppt_preview(compcard_url)
    if ext in IMAGE_EXTS:
        return compcard_url
    return None
