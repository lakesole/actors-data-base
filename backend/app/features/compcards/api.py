import aiosqlite
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.errors import NotFound, error_json
from app.features.compcards import service
from app.features.compcards.service import NoPdfToMerge, PdfMergeFailed

# 주의: 현재 두 다운로드 모두 로그인 검사가 없다 (docs/found-issues.md #2)
router = APIRouter(prefix="/api/compcards", tags=["compcards"])


class SelectedIn(BaseModel):
    actor_ids: list[int] = Field(min_length=1)


@router.get("/merged.pdf", response_class=FileResponse)
async def merged_pdf(
    q: str = "",
    m: str = "",
    ai_query: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    sort: str = "",
    status_filter: str = "",
    db: aiosqlite.Connection = Depends(get_db),
):
    """배우 목록과 같은 검색 조건에 맞는 배우들의 PDF 컴카드를 하나로 합친다."""
    try:
        path, filename = await service.build_merged_pdf(
            db, ai_query, q=q, m=m, gender=gender, height_group=height_group,
            birth_group=birth_group, sort=sort, status_filter=status_filter,
        )
    except NoPdfToMerge:
        raise NotFound("통합 가능한 PDF 파일이 없습니다.")
    except PdfMergeFailed as e:
        return error_json(500, f"PDF 병합 중 오류 발생: {e}", "PDF_MERGE_FAILED")
    return FileResponse(path=path, media_type="application/pdf", filename=filename)


@router.post("/selected.pdf", response_class=FileResponse)
async def selected_pdf(body: SelectedIn, db: aiosqlite.Connection = Depends(get_db)):
    try:
        path = await service.build_selected_pdf(db, body.actor_ids)
    except NoPdfToMerge:
        raise NotFound("선택한 배우 중 다운로드 가능한 PDF가 없습니다.")
    except PdfMergeFailed as e:
        return error_json(500, f"선택 PDF 병합 중 오류 발생: {e}", "PDF_MERGE_FAILED")
    return FileResponse(path=path, media_type="application/pdf", filename="선택컴카드.pdf")
