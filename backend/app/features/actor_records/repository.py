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


async def get(db: aiosqlite.Connection, table: str, actor_id: int, item_id: int) -> dict | None:
    cur = await db.execute(f"SELECT * FROM {table} WHERE id=? AND actor_id=?", (item_id, actor_id))
    row = await cur.fetchone()
    return dict(row) if row else None


async def insert(db: aiosqlite.Connection, table: str, date_col: str, actor_id: int, record_date: str, content: str, created_at: str):
    await db.execute(f"""
        INSERT INTO {table} (actor_id, {date_col}, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (actor_id, record_date, content, created_at))


async def update(db: aiosqlite.Connection, table: str, date_col: str, actor_id: int, item_id: int, record_date: str, content: str):
    await db.execute(f"""
        UPDATE {table}
        SET {date_col}=?, content=?
        WHERE id=? AND actor_id=?
    """, (record_date, content, item_id, actor_id))


async def delete(db: aiosqlite.Connection, table: str, actor_id: int, item_id: int):
    await db.execute(f"DELETE FROM {table} WHERE id=? AND actor_id=?", (item_id, actor_id))


async def class_log_exists(db: aiosqlite.Connection, actor_id: int, meet_date: str, content: str) -> bool:
    cur = await db.execute("""
        SELECT id
        FROM class_logs
        WHERE actor_id = ?
          AND meet_date = ?
          AND content = ?
        LIMIT 1
    """, (actor_id, meet_date, content))
    return await cur.fetchone() is not None
