import aiosqlite


async def list_all_lessons(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("""
        SELECT
            tl.id,
            tl.lesson_name,
            tl.lesson_days,
            tl.teacher_user_id,
            u.display_name AS teacher_name
        FROM teacher_lessons tl
        JOIN users u
          ON u.id = tl.teacher_user_id
        ORDER BY
            CASE WHEN tl.lesson_name IS NULL OR tl.lesson_name = '' THEN 1 ELSE 0 END,
            tl.lesson_name ASC,
            tl.id DESC
    """)
    return [dict(r) for r in await cur.fetchall()]


async def get_lesson(db: aiosqlite.Connection, lesson_id: int, teacher_user_id: int | None = None) -> dict | None:
    """teacher_user_id를 주면 그 선생님의 수업일 때만 반환한다."""
    if teacher_user_id is not None:
        cur = await db.execute("""
            SELECT
                tl.id,
                tl.lesson_name,
                tl.lesson_days,
                tl.teacher_user_id
            FROM teacher_lessons tl
            WHERE tl.id = ?
              AND tl.teacher_user_id = ?
        """, (lesson_id, teacher_user_id))
    else:
        cur = await db.execute("""
            SELECT
                tl.id,
                tl.lesson_name,
                tl.lesson_days,
                tl.teacher_user_id
            FROM teacher_lessons tl
            WHERE tl.id = ?
        """, (lesson_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def list_lesson_actors_with_attendance(db: aiosqlite.Connection, lesson_id: int, attendance_date: str) -> list[dict]:
    cur = await db.execute("""
        SELECT
            a.id,
            a.name,
            a.gender,
            a.birth_year,
            a.phone_last4,
            al.status,
            al.phone_input,
            al.feedback
        FROM lesson_actor_assignments la
        JOIN actors a
          ON a.id = la.actor_id
        LEFT JOIN attendance_logs al
          ON al.lesson_id = la.lesson_id
         AND al.actor_id = la.actor_id
         AND al.attendance_date = ?
        WHERE la.lesson_id = ?
        ORDER BY a.name ASC, a.id DESC
    """, (attendance_date, lesson_id))
    return [dict(r) for r in await cur.fetchall()]


async def list_lesson_actor_phones(db: aiosqlite.Connection, lesson_id: int) -> list[dict]:
    cur = await db.execute("""
        SELECT
            a.id,
            a.phone_last4
        FROM lesson_actor_assignments la
        JOIN actors a
          ON a.id = la.actor_id
        WHERE la.lesson_id = ?
    """, (lesson_id,))
    return [dict(r) for r in await cur.fetchall()]


async def list_lesson_assignments(db: aiosqlite.Connection) -> list[dict]:
    """전체 수업-배우 배정. 오늘 출석 대상을 고를 때 쓴다."""
    cur = await db.execute("""
        SELECT
            tl.id AS lesson_id,
            tl.lesson_name,
            tl.lesson_days,
            a.id AS actor_id,
            a.name,
            a.phone_last4
        FROM teacher_lessons tl
        JOIN lesson_actor_assignments la
          ON la.lesson_id = tl.id
        JOIN actors a
          ON a.id = la.actor_id
        ORDER BY tl.id DESC, a.name ASC
    """)
    return [dict(r) for r in await cur.fetchall()]


async def get_lesson_name(db: aiosqlite.Connection, lesson_id: int) -> str:
    cur = await db.execute("""
        SELECT lesson_name
        FROM teacher_lessons
        WHERE id = ?
    """, (lesson_id,))
    row = await cur.fetchone()
    return str(row[0]).strip() if row and row[0] else ""


async def get_status(db: aiosqlite.Connection, lesson_id: int, actor_id: int, attendance_date: str) -> str | None:
    cur = await db.execute("""
        SELECT id, status
        FROM attendance_logs
        WHERE lesson_id = ?
          AND actor_id = ?
          AND attendance_date = ?
    """, (lesson_id, actor_id, attendance_date))
    row = await cur.fetchone()
    return row["status"] if row else None


async def upsert_with_feedback(
    db: aiosqlite.Connection,
    lesson_id: int,
    actor_id: int,
    attendance_date: str,
    status: str,
    phone_input: str,
    feedback: str,
    checked_by_user_id: int,
    now: str,
):
    """출석부 저장. 피드백까지 덮어쓴다."""
    await db.execute("""
        INSERT INTO attendance_logs (
            lesson_id, actor_id, attendance_date, status,
            phone_input, feedback, checked_by_user_id,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(lesson_id, actor_id, attendance_date)
        DO UPDATE SET
            status = excluded.status,
            phone_input = excluded.phone_input,
            feedback = excluded.feedback,
            checked_by_user_id = excluded.checked_by_user_id,
            updated_at = excluded.updated_at
    """, (lesson_id, actor_id, attendance_date, status, phone_input, feedback, checked_by_user_id, now, now))


async def upsert_kiosk_check(
    db: aiosqlite.Connection,
    lesson_id: int,
    actor_id: int,
    attendance_date: str,
    phone_input: str,
    checked_by_user_id: int,
    now: str,
):
    """키오스크 출석 체크. 기존 피드백은 건드리지 않는다."""
    await db.execute("""
        INSERT INTO attendance_logs (
            lesson_id, actor_id, attendance_date, status,
            phone_input, feedback, checked_by_user_id,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(lesson_id, actor_id, attendance_date)
        DO UPDATE SET
            status = excluded.status,
            phone_input = excluded.phone_input,
            checked_by_user_id = excluded.checked_by_user_id,
            updated_at = excluded.updated_at
    """, (lesson_id, actor_id, attendance_date, "출석", phone_input, "", checked_by_user_id, now, now))
