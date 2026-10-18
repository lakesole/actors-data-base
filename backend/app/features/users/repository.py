import aiosqlite


async def list_users(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("""
        SELECT id, username, display_name, role, is_active, created_at
        FROM users
        ORDER BY
            CASE role
                WHEN 'admin' THEN 0
                WHEN 'staff' THEN 1
                WHEN 'teacher' THEN 2
                ELSE 9
            END,
            created_at DESC,
            id DESC
    """)
    return [dict(r) for r in await cur.fetchall()]


async def get_user(db: aiosqlite.Connection, user_id: int) -> dict | None:
    cur = await db.execute("""
        SELECT id, username, display_name, role, is_active, created_at
        FROM users
        WHERE id = ?
    """, (user_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def username_exists(db: aiosqlite.Connection, username: str) -> bool:
    cur = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
    return await cur.fetchone() is not None


async def any_admin_exists(db: aiosqlite.Connection) -> bool:
    cur = await db.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    return await cur.fetchone() is not None


async def count_admins(db: aiosqlite.Connection) -> int:
    cur = await db.execute("""
        SELECT COUNT(*) FROM users
        WHERE role = 'admin'
    """)
    return (await cur.fetchone())[0]


async def insert_user(
    db: aiosqlite.Connection,
    username: str,
    password_hash: str,
    display_name: str,
    role: str,
    created_at: str,
) -> int:
    cur = await db.execute("""
        INSERT INTO users (username, password_hash, display_name, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username, password_hash, display_name, role, 1, created_at))
    return cur.lastrowid


async def set_active(db: aiosqlite.Connection, user_id: int, is_active: int):
    await db.execute("""
        UPDATE users
        SET is_active = ?
        WHERE id = ?
    """, (is_active, user_id))


async def set_role(db: aiosqlite.Connection, user_id: int, role: str):
    await db.execute("""
        UPDATE users
        SET role = ?
        WHERE id = ?
    """, (role, user_id))


async def set_password_hash(db: aiosqlite.Connection, user_id: int, password_hash: str):
    await db.execute("""
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
    """, (password_hash, user_id))


async def delete_user(db: aiosqlite.Connection, user_id: int):
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
