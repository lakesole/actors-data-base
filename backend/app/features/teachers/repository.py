import aiosqlite


async def list_teachers_with_profile(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("""
        SELECT
            u.id,
            u.username,
            u.display_name,
            u.role,
            u.is_active,
            u.created_at,
            tp.lesson_subject,
            tp.lesson_days
        FROM users u
        LEFT JOIN teacher_profiles tp
          ON tp.user_id = u.id
        WHERE u.role = 'teacher'
        ORDER BY u.display_name ASC, u.id DESC
    """)
    return [dict(r) for r in await cur.fetchall()]


async def list_active_teachers(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("""
        SELECT
            u.id,
            u.display_name,
            u.username,
            COALESCE(tp.lesson_subject, '') AS lesson_subject,
            COALESCE(tp.lesson_days, '') AS lesson_days
        FROM users u
        LEFT JOIN teacher_profiles tp
          ON tp.user_id = u.id
        WHERE u.role = 'teacher'
          AND u.is_active = 1
        ORDER BY u.display_name ASC, u.id DESC
    """)
    return [dict(r) for r in await cur.fetchall()]


async def list_lessons(db: aiosqlite.Connection, teacher_user_id: int) -> list[dict]:
    cur = await db.execute("""
        SELECT id, teacher_user_id, lesson_name, lesson_days, created_at
        FROM teacher_lessons
        WHERE teacher_user_id = ?
        ORDER BY id DESC
    """, (teacher_user_id,))
    return [dict(r) for r in await cur.fetchall()]


async def list_lesson_actors(db: aiosqlite.Connection, lesson_id: int) -> list[dict]:
    cur = await db.execute("""
        SELECT
            a.id,
            a.name,
            a.teacher_user_id
        FROM lesson_actor_assignments la
        JOIN actors a
          ON a.id = la.actor_id
        WHERE la.lesson_id = ?
        ORDER BY a.name ASC, a.id DESC
    """, (lesson_id,))
    return [dict(r) for r in await cur.fetchall()]


async def get_user_role(db: aiosqlite.Connection, user_id: int) -> dict | None:
    cur = await db.execute("""
        SELECT id, role
        FROM users
        WHERE id = ?
    """, (user_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def upsert_profile(db: aiosqlite.Connection, user_id: int, lesson_subject: str, lesson_days: str, updated_at: str):
    await db.execute("""
        INSERT INTO teacher_profiles (user_id, lesson_subject, lesson_days, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            lesson_subject = excluded.lesson_subject,
            lesson_days = excluded.lesson_days,
            updated_at = excluded.updated_at
    """, (user_id, lesson_subject, lesson_days, updated_at))


async def insert_empty_profile_if_missing(db: aiosqlite.Connection, user_id: int, updated_at: str):
    await db.execute("""
        INSERT OR IGNORE INTO teacher_profiles (user_id, lesson_subject, lesson_days, updated_at)
        VALUES (?, '', '', ?)
    """, (user_id, updated_at))


async def insert_lesson(db: aiosqlite.Connection, teacher_user_id: int, lesson_name: str, lesson_days: str, created_at: str):
    await db.execute("""
        INSERT INTO teacher_lessons (
            teacher_user_id, lesson_name, lesson_days, created_at
        )
        VALUES (?, ?, ?, ?)
    """, (teacher_user_id, lesson_name, lesson_days, created_at))


async def get_lesson(db: aiosqlite.Connection, lesson_id: int) -> dict | None:
    cur = await db.execute("""
        SELECT id, teacher_user_id
        FROM teacher_lessons
        WHERE id = ?
    """, (lesson_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def delete_lesson_assignments(db: aiosqlite.Connection, lesson_id: int):
    await db.execute("""
        DELETE FROM lesson_actor_assignments
        WHERE lesson_id = ?
    """, (lesson_id,))


async def delete_lesson(db: aiosqlite.Connection, lesson_id: int):
    await db.execute("""
        DELETE FROM teacher_lessons
        WHERE id = ?
    """, (lesson_id,))


async def insert_assignment(db: aiosqlite.Connection, lesson_id: int, actor_id: int, created_at: str):
    await db.execute("""
        INSERT OR IGNORE INTO lesson_actor_assignments (
            lesson_id, actor_id, created_at
        )
        VALUES (?, ?, ?)
    """, (lesson_id, actor_id, created_at))
