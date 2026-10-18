"""
배우 기록 5종 API. 종류마다 같은 모양의 라우트를 등록한다.
    GET    /api/actors/{actor_id}/<api_path>
    POST   /api/actors/{actor_id}/<api_path>
    GET    /api/actors/{actor_id}/<api_path>/{item_id}
    PATCH  /api/actors/{actor_id}/<api_path>/{item_id}
    DELETE /api/actors/{actor_id}/<api_path>/{item_id}
<api_path>: class-logs, auditions, casting-management, casting-meetings, first-meetings
"""
import aiosqlite
from fastapi import APIRouter, Depends, Response

from app.core.auth import current_user, require_login
from app.core.database import get_db
from app.core.errors import NotFound
from app.features.actor_records import service
from app.features.actor_records.schemas import RecordIn, RecordOut
from app.features.actor_records.service import RECORD_TYPES, RecordType

router = APIRouter(prefix="/api/actors", tags=["actor_records"])


def _to_out(t: RecordType, row: dict) -> dict:
    return {
        "id": row["id"],
        "actor_id": row["actor_id"],
        "date": row[t.date_field],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def _register(t: RecordType):
    base = f"/{{actor_id}}/{t.api_path}"

    async def get_or_404(db, actor_id: int, item_id: int) -> dict:
        row = await service.get_record(db, t.path, actor_id, item_id)
        if not row:
            raise NotFound("기록을 찾을 수 없습니다.")
        return _to_out(t, row)

    @router.get(base, response_model=list[RecordOut], name=f"api_{t.path}_list")
    async def list_records(
        actor_id: int,
        user: dict | None = Depends(current_user),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        rows = await service.list_records_for_user(db, user, t.path, actor_id)
        return [_to_out(t, r) for r in rows]

    @router.post(base, response_model=RecordOut, status_code=201, name=f"api_{t.path}_create")
    async def create_record(
        actor_id: int,
        body: RecordIn,
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        item_id = await service.create_record(db, user, t.path, actor_id, body.date, body.content)
        return await get_or_404(db, actor_id, item_id)

    @router.get(f"{base}/{{item_id}}", response_model=RecordOut, name=f"api_{t.path}_get")
    async def get_record(
        actor_id: int,
        item_id: int,
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        """수정 화면용 조회. 수정 권한이 있어야 한다."""
        await service.ensure_can_edit(db, user, actor_id)
        return await get_or_404(db, actor_id, item_id)

    @router.patch(f"{base}/{{item_id}}", response_model=RecordOut, name=f"api_{t.path}_update")
    async def update_record(
        actor_id: int,
        item_id: int,
        body: RecordIn,
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        await service.update_record(db, user, t.path, actor_id, item_id, body.date, body.content)
        return await get_or_404(db, actor_id, item_id)

    @router.delete(f"{base}/{{item_id}}", status_code=204, name=f"api_{t.path}_delete")
    async def delete_record(
        actor_id: int,
        item_id: int,
        user: dict = Depends(require_login),
        db: aiosqlite.Connection = Depends(get_db),
    ):
        await service.delete_record(db, user, t.path, actor_id, item_id)
        return Response(status_code=204)


for record_type in RECORD_TYPES.values():
    _register(record_type)
