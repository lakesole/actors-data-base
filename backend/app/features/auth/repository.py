import aiosqlite


async def find_by_username(db: aiosqlite.Connection, username: str) -> dict | None:
    cur = await db.execute("""
        SELECT id, username, password_hash, display_name, role, is_active
        FROM users
        WHERE username = ?
    """, (username,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_password_hash(db: aiosqlite.Connection, user_id: int) -> str | None:
    cur = await db.execute("""
        SELECT id, password_hash
        FROM users
        WHERE id = ?
    """, (user_id,))
    row = await cur.fetchone()
    return row["password_hash"] if row else None


async def update_password_hash(db: aiosqlite.Connection, user_id: int, password_hash: str):
    await db.execute("""
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
    """, (password_hash, user_id))
