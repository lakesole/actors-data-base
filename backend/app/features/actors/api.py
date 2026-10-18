import aiosqlite
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from app.core.auth import current_user, require_admin_or_staff, require_login
from app.core.database import get_db
from app.core.errors import NotFound
from app.features.actors import service
from app.features.actors.forms import actor_form
from app.features.actors.schemas import ActorBrief, ActorListOut, ActorOut, CreatedOut, VideoOut
from app.features.actors.service import ActorForm

router = APIRouter(prefix="/api/actors", tags=["actors"])


@router.get("", response_model=ActorListOut)
async def list_actors(
    q: str = "",
    m: str = "",
    ai_query: str = "",
    gender: str = "",
    height_group: str = "",
    birth_group: str = "",
    sort: str = "",
    status_filter: str = "",
    lesson_id: str = "",
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=200),
    user: dict | None = Depends(current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """배우 목록. 로그인하지 않으면 보기 전용, teacher는 담당 배우만 보인다."""
    f = service.make_filters(q, m, gender, height_group, birth_group, sort, status_filter)
    data = await service.get_index_data(db, user, f, ai_query.strip(), lesson_id.strip(), page, per_page)

    scores = {actor["id"]: (score, matched) for actor, score, matched in data["ai_scored_results"] or []}
    items = []
    for actor in data["actors"]:
        if actor["id"] in scores:
            actor["ai_score"], actor["ai_matched"] = scores[actor["id"]]
        items.append(actor)

    return {
        "items": items,
        "total_count": data["total_count"],
        "total_pages": data["total_pages"],
        "page": data["page"],
        "per_page": per_page,
        "ai_parsed": data["ai_parsed"],
        "teacher_lessons": data["teacher_lessons"],
    }


@router.get("/simple", response_model=list[ActorBrief], dependencies=[Depends(require_admin_or_staff)])
async def list_actors_simple(db: aiosqlite.Connection = Depends(get_db)):
    """수업 배정 화면 등에서 쓰는 전체 배우 이름 목록."""
    return await service.list_actors_simple(db)


@router.get("/{actor_id}", response_model=ActorOut)
async def get_actor(
    actor_id: int,
    user: dict | None = Depends(current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    data = await service.get_detail_data(db, user, actor_id, "compcard")
    if data is None:
        raise NotFound("배우를 찾을 수 없습니다.")
    return data["actor"]


@router.get("/{actor_id}/videos", response_model=list[VideoOut])
async def list_videos(
    actor_id: int,
    user: dict | None = Depends(current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    return await service.list_videos(db, user, actor_id)


@router.post("", response_model=CreatedOut, status_code=201)
async def create_actor(
    form: ActorForm = Depends(actor_form),
    photo: UploadFile | None = File(None),
    compcard: UploadFile | None = File(None),
    # 주의: 유니온 타입이라 여러 파일 중 마지막 1개만 들어온다 (docs/found-issues.md #13)
    acting_videos: list[UploadFile] | UploadFile | None = File(None),
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    """multipart/form-data. 필드는 화면의 배우 추가 폼과 같다."""
    service.ensure_can_create(user)
    return {"id": await service.create_actor(db, form, photo, compcard, acting_videos)}


@router.patch("/{actor_id}", response_model=ActorOut)
async def update_actor(
    actor_id: int,
    form: ActorForm = Depends(actor_form),
    photo: UploadFile | None = File(None),
    compcard: UploadFile | None = File(None),
    acting_videos: list[UploadFile] | UploadFile | None = File(None),
    user: dict = Depends(require_admin_or_staff),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    multipart/form-data. 텍스트 필드는 모두 보내야 한다 (보내지 않은 필드는 빈 값이 된다).
    파일은 보낸 것만 교체(사진, 컴카드)하거나 추가(연기영상)한다.
    """
    await service.update_actor(db, actor_id, form, photo, compcard, acting_videos)
    data = await service.get_detail_data(db, user, actor_id, "compcard")
    return data["actor"]


@router.delete("/{actor_id}", status_code=204)
async def delete_actor(
    actor_id: int,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.delete_actor(db, user, actor_id)
    return Response(status_code=204)


@router.delete("/{actor_id}/videos/{video_id}", status_code=204)
async def delete_video(
    actor_id: int,
    video_id: int,
    user: dict = Depends(require_login),
    db: aiosqlite.Connection = Depends(get_db),
):
    await service.delete_video(db, user, actor_id, video_id)
    return Response(status_code=204)
