import os
import uuid

import aiosqlite
from pypdf import PdfWriter

from app.core.config import MERGED_DIR
from app.core.files import IMAGE_EXTS, ensure_dirs, safe_download_filename, url_to_fs_path
from app.features.actors import service as actors_service
from app.features.compcards import repository
from app.features.compcards.pdf_convert import make_ppt_preview


class NoPdfToMerge(Exception):
    pass


class PdfMergeFailed(Exception):
    pass


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


def _find_pdf_path(actor: dict) -> str | None:
    """컴카드 원본, 미리보기 순으로 실제 존재하는 PDF 파일 경로를 찾는다."""
    compcard_url = actor.get("compcard_path")
    preview_url = actor.get("compcard_preview_path")

    candidate_urls = []
    if compcard_url:
        candidate_urls.append(compcard_url)
    if preview_url and preview_url != compcard_url:
        candidate_urls.append(preview_url)

    for url in candidate_urls:
        fs_path = url_to_fs_path(url)
        if os.path.exists(fs_path) and fs_path.lower().endswith(".pdf"):
            return fs_path
    return None


def _merge(pdf_paths: list[str], output_path: str):
    writer = PdfWriter()
    try:
        for pdf_path in pdf_paths:
            writer.append(pdf_path)
        with open(output_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        raise PdfMergeFailed(str(e))


async def build_merged_pdf(db: aiosqlite.Connection, ai_query: str = "", **filters) -> tuple[str, str]:
    """
    배우 목록과 같은 검색 조건(q, m, gender, height_group, birth_group, sort, status_filter)에 맞는
    배우들의 PDF 컴카드를 하나로 합친다. 반환: (파일 경로, 다운로드 파일명)
    """
    f = actors_service.make_filters(**filters)
    actors, _, _ = await actors_service.search_actors(db, f, (ai_query or "").strip())
    pdf_paths = [p for p in (_find_pdf_path(a) for a in actors) if p]
    if not pdf_paths:
        raise NoPdfToMerge()

    ensure_dirs()
    filename = safe_download_filename("merged_compcards", "pdf")
    output_path = os.path.join(MERGED_DIR, filename)
    _merge(pdf_paths, output_path)
    return output_path, filename


async def build_selected_pdf(db: aiosqlite.Connection, actor_ids: list[int]) -> str:
    """선택한 배우들의 PDF 컴카드를 하나로 합친다. 반환: 파일 경로"""
    ensure_dirs()
    actors = await repository.list_compcards_by_actor_ids(db, actor_ids)
    pdf_paths = [p for p in (_find_pdf_path(a) for a in actors) if p]
    if not pdf_paths:
        raise NoPdfToMerge()

    output_path = os.path.join(MERGED_DIR, f"selected_compcards_{uuid.uuid4().hex[:8]}.pdf")
    _merge(pdf_paths, output_path)
    return output_path
