"""
배우 기록 5종의 공통 SQL.

다섯 테이블 모두 (id, actor_id, <날짜>, content, created_at) 구조이고 날짜 컬럼 이름만 다르다.
테이블/컬럼 이름은 service의 RECORD_TYPES 상수에서만 오므로 f-string을 써도 안전하다.
"""
import aiosqlite


async def list_by_actor(db: aiosqlite.Connection, table: str, date_col: str, actor_id: int) -> list[dict]:
    cur = await db.execute(
        f"SELECT * FROM {table} WHERE actor_id=? ORDER BY {date_col} DESC, id DESC",
        (actor_id,)
    )
    return [dict(r) for r in await cur.fetchall()]
