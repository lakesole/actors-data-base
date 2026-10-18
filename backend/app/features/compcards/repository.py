import aiosqlite


async def list_compcards_by_actor_ids(db: aiosqlite.Connection, actor_ids: list[int]) -> list[dict]:
    placeholders = ",".join(["?"] * len(actor_ids))
    cur = await db.execute(f"""
        SELECT id, name, compcard_path, compcard_preview_path
        FROM actors
        WHERE id IN ({placeholders})
        ORDER BY id DESC
    """, actor_ids)
    return [dict(r) for r in await cur.fetchall()]
