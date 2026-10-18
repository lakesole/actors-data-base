import aiosqlite


async def list_actors_simple(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("""
        SELECT id, name, teacher_user_id
        FROM actors
        ORDER BY name ASC, id DESC
    """)
    return [dict(r) for r in await cur.fetchall()]
