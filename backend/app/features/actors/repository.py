from dataclasses import dataclass

import aiosqlite

HEIGHT_RANGES = {"150": (150, 160), "160": (160, 170), "170": (170, 180), "180": (180, 190)}
BIRTH_RANGES = {"1980": (1980, 1989), "1990": (1990, 1999), "2000": (2000, 2009), "2010": (2010, 2019)}

# INSERT/UPDATE 할 때 쓰는 컬럼 순서
ACTOR_COLUMNS = [
    "name", "birth_year", "height_cm", "weight_kg", "photo_path", "photo_thumb_path", "bio",
    "school", "hobby", "specialty", "contract_date", "contract_end_date",
    "manager_name", "gender", "compcard_path", "compcard_preview_path", "teacher_user_id", "phone_last4",
]


@dataclass
class ActorFilters:
    """목록 검색 조건. 값은 service에서 공백 제거된 상태로 들어온다."""
    q: str = ""
    m: str = ""
    gender: str = ""
    height_group: str = ""
    birth_group: str = ""
    sort: str = ""
    status_filter: str = ""


def build_actor_filters(f: ActorFilters, teacher_user_id: int | None = None, prefix: str = ""):
    """WHERE 조건 목록과 파라미터를 만든다. prefix는 테이블 별칭("a.")이다."""
    wheres = []
    params = []

    if f.q:
        wheres.append(f"{prefix}name LIKE ?")
        params.append(f"%{f.q}%")

    if f.m:
        wheres.append(f"{prefix}manager_name LIKE ?")
        params.append(f"%{f.m}%")

    if f.gender:
        wheres.append(f"{prefix}gender = ?")
        params.append(f.gender)

    if teacher_user_id is not None:
        wheres.append(f"{prefix}teacher_user_id = ?")
        params.append(teacher_user_id)

    if f.height_group in HEIGHT_RANGES:
        wheres.append(f"{prefix}height_cm >= ? AND {prefix}height_cm < ?")
        params.extend(HEIGHT_RANGES[f.height_group])

    if f.birth_group in BIRTH_RANGES:
        wheres.append(f"{prefix}birth_year BETWEEN ? AND ?")
        params.extend(BIRTH_RANGES[f.birth_group])

    if f.status_filter == "active":
        wheres.append(f"""
            (
                {prefix}contract_end_date IS NULL
                OR {prefix}contract_end_date = ''
                OR date({prefix}contract_end_date) >= date('now','localtime')
            )
        """)
    elif f.status_filter == "expired":
        wheres.append(f"""
            {prefix}contract_end_date IS NOT NULL
            AND {prefix}contract_end_date != ''
            AND date({prefix}contract_end_date) < date('now','localtime')
        """)

    return wheres, params


def build_actor_order_by(sort: str = "", prefix: str = "") -> str:
    if sort == "youngest":
        return f"ORDER BY {prefix}birth_year DESC, {prefix}id DESC"
    elif sort == "oldest":
        return f"ORDER BY {prefix}birth_year ASC, {prefix}id DESC"
    elif sort == "new_contract":
        return f"""
        ORDER BY
            CASE WHEN {prefix}contract_date IS NULL OR {prefix}contract_date = '' THEN 1 ELSE 0 END,
            {prefix}contract_date DESC,
            {prefix}id DESC
        """
    elif sort == "old_contract":
        return f"""
        ORDER BY
            CASE WHEN {prefix}contract_date IS NULL OR {prefix}contract_date = '' THEN 1 ELSE 0 END,
            {prefix}contract_date ASC,
            {prefix}id DESC
        """
    return f"ORDER BY {prefix}id DESC"


# ---------- 목록 ----------

async def list_actors(db: aiosqlite.Connection, f: ActorFilters, teacher_user_id: int | None = None) -> list[dict]:
    wheres, params = build_actor_filters(f, teacher_user_id)
    base_where = " WHERE " + " AND ".join(wheres) if wheres else ""

    cur = await db.execute(f"""
        SELECT * FROM actors
        {base_where}
        {build_actor_order_by(f.sort)}
    """, params)
    return [dict(r) for r in await cur.fetchall()]


async def list_actors_page(
    db: aiosqlite.Connection,
    f: ActorFilters,
    page: int,
    per_page: int,
    teacher_user_id: int | None = None,
) -> tuple[list[dict], int]:
    wheres, params = build_actor_filters(f, teacher_user_id)
    base_where = " WHERE " + " AND ".join(wheres) if wheres else ""
    offset = (page - 1) * per_page

    cur = await db.execute(f"SELECT COUNT(*) FROM actors {base_where}", params)
    total_count = (await cur.fetchone())[0]

    cur = await db.execute(f"""
        SELECT * FROM actors
        {base_where}
        {build_actor_order_by(f.sort)}
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    return [dict(r) for r in await cur.fetchall()], total_count


async def list_teacher_visible_actors_page(
    db: aiosqlite.Connection,
    teacher_user_id: int,
    f: ActorFilters,
    lesson_id: str,
    page: int,
    per_page: int,
) -> tuple[list[dict], int]:
    """선생님에게 보이는 배우: 직접 담당이거나 본인 수업에 배정된 배우."""
    base_sql = """
        FROM actors a
        WHERE (
            a.teacher_user_id = ?
            OR a.id IN (
                SELECT la.actor_id
                FROM lesson_actor_assignments la
                JOIN teacher_lessons tl
                  ON tl.id = la.lesson_id
                WHERE tl.teacher_user_id = ?
            )
        )
    """
    params = [teacher_user_id, teacher_user_id]
    wheres = []

    # 수업 필터
    if lesson_id:
        wheres.append("""
            a.id IN (
                SELECT la.actor_id
                FROM lesson_actor_assignments la
                JOIN teacher_lessons tl
                  ON tl.id = la.lesson_id
                WHERE tl.teacher_user_id = ?
                  AND la.lesson_id = ?
            )
        """)
        params.extend([teacher_user_id, int(lesson_id)])

    filter_wheres, filter_params = build_actor_filters(f, prefix="a.")
    wheres += filter_wheres
    params += filter_params

    extra_where = " AND " + " AND ".join(wheres) if wheres else ""
    offset = (page - 1) * per_page

    cur = await db.execute(f"SELECT COUNT(DISTINCT a.id) {base_sql} {extra_where}", params)
    total_count = (await cur.fetchone())[0]

    cur = await db.execute(f"""
        SELECT DISTINCT a.*
        {base_sql}
        {extra_where}
        {build_actor_order_by(f.sort, prefix="a.")}
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    return [dict(r) for r in await cur.fetchall()], total_count


async def list_actors_simple(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("""
        SELECT id, name, teacher_user_id
        FROM actors
        ORDER BY name ASC, id DESC
    """)
    return [dict(r) for r in await cur.fetchall()]


# ---------- 단건 ----------

async def get_actor(db: aiosqlite.Connection, actor_id: int) -> dict | None:
    cur = await db.execute("SELECT * FROM actors WHERE id = ?", (actor_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_actor_with_teacher(db: aiosqlite.Connection, actor_id: int) -> dict | None:
    cur = await db.execute("""
        SELECT
            a.*,
            u.display_name AS teacher_user_name
        FROM actors a
        LEFT JOIN users u
        ON a.teacher_user_id = u.id
        WHERE a.id = ?
    """, (actor_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def is_directly_assigned(db: aiosqlite.Connection, actor_id: int, teacher_user_id: int) -> bool:
    cur = await db.execute("""
        SELECT id
        FROM actors
        WHERE id = ? AND teacher_user_id = ?
    """, (actor_id, teacher_user_id))
    return await cur.fetchone() is not None


async def is_assigned_by_lesson(db: aiosqlite.Connection, actor_id: int, teacher_user_id: int) -> bool:
    cur = await db.execute("""
        SELECT la.id
        FROM lesson_actor_assignments la
        JOIN teacher_lessons tl
          ON tl.id = la.lesson_id
        WHERE la.actor_id = ?
          AND tl.teacher_user_id = ?
        LIMIT 1
    """, (actor_id, teacher_user_id))
    return await cur.fetchone() is not None


# ---------- 생성 / 수정 / 삭제 ----------

async def insert_actor(db: aiosqlite.Connection, values: dict) -> int:
    cur = await db.execute(f"""
        INSERT INTO actors (
            {", ".join(ACTOR_COLUMNS)}
        )
        VALUES ({", ".join("?" * len(ACTOR_COLUMNS))})
    """, [values[c] for c in ACTOR_COLUMNS])
    return cur.lastrowid


async def update_actor(db: aiosqlite.Connection, actor_id: int, values: dict):
    await db.execute(f"""
        UPDATE actors
        SET {", ".join(f"{c} = ?" for c in ACTOR_COLUMNS)}
        WHERE id = ?
    """, [values[c] for c in ACTOR_COLUMNS] + [actor_id])


async def get_actor_files(db: aiosqlite.Connection, actor_id: int) -> dict | None:
    cur = await db.execute("""
        SELECT photo_path, compcard_path, compcard_preview_path, acting_video_path
        FROM actors WHERE id=?
    """, (actor_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def delete_actor(db: aiosqlite.Connection, actor_id: int):
    await db.execute("DELETE FROM actors WHERE id=?", (actor_id,))


# ---------- 연기영상 ----------

async def list_videos(db: aiosqlite.Connection, actor_id: int) -> list[dict]:
    cur = await db.execute(
        "SELECT * FROM acting_videos WHERE actor_id=? ORDER BY created_at DESC, id DESC",
        (actor_id,)
    )
    return [dict(r) for r in await cur.fetchall()]


async def list_video_paths(db: aiosqlite.Connection, actor_id: int) -> list[str]:
    cur = await db.execute("SELECT video_path FROM acting_videos WHERE actor_id=?", (actor_id,))
    return [r["video_path"] for r in await cur.fetchall()]


async def insert_video(db: aiosqlite.Connection, actor_id: int, video_path: str, original_name: str, created_at: str):
    await db.execute("""
        INSERT INTO acting_videos (actor_id, video_path, original_name, created_at)
        VALUES (?, ?, ?, ?)
    """, (actor_id, video_path, original_name, created_at))


async def get_video_path(db: aiosqlite.Connection, actor_id: int, video_id: int) -> str | None:
    cur = await db.execute(
        "SELECT video_path FROM acting_videos WHERE id=? AND actor_id=?",
        (video_id, actor_id)
    )
    row = await cur.fetchone()
    return row["video_path"] if row else None


async def delete_video(db: aiosqlite.Connection, actor_id: int, video_id: int):
    await db.execute("DELETE FROM acting_videos WHERE id=? AND actor_id=?", (video_id, actor_id))


# ---------- 시작 시 데이터 정리 ----------

async def list_dates_for_normalize(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("""
        SELECT id, birth_year, contract_date, contract_end_date
        FROM actors
    """)
    return [dict(r) for r in await cur.fetchall()]


async def update_dates(db: aiosqlite.Connection, actor_id: int, birth_year, contract_date, contract_end_date):
    await db.execute("""
        UPDATE actors
        SET birth_year=?,
            contract_date=?,
            contract_end_date=?
        WHERE id=?
    """, (birth_year, contract_date, contract_end_date, actor_id))
