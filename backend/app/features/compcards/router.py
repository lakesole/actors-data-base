import aiosqlite
from fastapi import APIRouter, Depends, Form
from fastapi.responses import FileResponse, PlainTextResponse

from app.core.database import get_db
from app.features.compcards import service
from app.features.compcards.service import NoPdfToMerge, PdfMergeFailed

# 주의: 현재 두 다운로드 모두 로그인 검사가 없다 (docs/found-issues.md #2)
router = APIRouter(prefix="/download")


@router.get("/merged-compcards/pdf")
async def download_merged_compcards_pdf(
    q: str | None = None,
    m: str | None = None,
    ai_query: str | None = None,
    gender: str | None = None,
    height_group: str | None = None,
    birth_group: str | None = None,
    sort: str | None = None,
    status_filter: str | None = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        path, filename = await service.build_merged_pdf(
            db, ai_query, q=q, m=m, gender=gender, height_group=height_group,
            birth_group=birth_group, sort=sort, status_filter=status_filter,
        )
    except NoPdfToMerge:
        return PlainTextResponse("통합 가능한 PDF 파일이 없습니다.", status_code=404)
    except PdfMergeFailed as e:
        return PlainTextResponse(f"PDF 병합 중 오류 발생: {e}", status_code=500)

    return FileResponse(path=path, media_type="application/pdf", filename=filename)


@router.post("/selected-compcards/pdf")
async def download_selected_compcards_pdf(
    actor_ids: list[int] = Form(...),
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        path = await service.build_selected_pdf(db, actor_ids)
    except NoPdfToMerge:
        return PlainTextResponse("선택한 배우 중 다운로드 가능한 PDF가 없습니다.", status_code=404)
    except PdfMergeFailed as e:
        return PlainTextResponse(f"선택 PDF 병합 중 오류 발생: {e}", status_code=500)

    return FileResponse(path=path, media_type="application/pdf", filename="선택컴카드.pdf")
