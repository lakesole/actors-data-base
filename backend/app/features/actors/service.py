import aiosqlite

from app.features.actors import repository


async def list_actors_simple(db: aiosqlite.Connection) -> list[dict]:
    """수업 배정 화면 등에서 쓰는 전체 배우 이름 목록."""
    return await repository.list_actors_simple(db)
