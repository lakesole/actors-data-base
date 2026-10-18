"""테이블 생성과 스키마 마이그레이션. 앱 시작 시 한 번 실행된다."""
from app.core.database import open_db


async def init_db():
    async with open_db() as db:
        # actors
        await db.execute("""
        CREATE TABLE IF NOT EXISTS actors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            birth_year INTEGER,
            height_cm REAL,
            weight_kg REAL,
            photo_path TEXT,
            bio TEXT,

            school TEXT,
            hobby TEXT,
            specialty TEXT,
            contract_date TEXT,
            manager_name TEXT,

            compcard_path TEXT,
            compcard_preview_path TEXT,

            acting_video_path TEXT
        )
        """)

        # ✅ 기존 DB에 컬럼이 없을 수도 있으니 안전하게 추가
        cur = await db.execute("PRAGMA table_info(actors)")
        cols = [r[1] for r in await cur.fetchall()]

        async def add_col_if_missing(col: str, col_type: str):
            if col not in cols:
                await db.execute(f"ALTER TABLE actors ADD COLUMN {col} {col_type}")

        await add_col_if_missing("compcard_preview_path", "TEXT")
        await add_col_if_missing("school", "TEXT")
        await add_col_if_missing("hobby", "TEXT")
        await add_col_if_missing("specialty", "TEXT")
        await add_col_if_missing("contract_date", "TEXT")
        await add_col_if_missing("contract_end_date", "TEXT")
        await add_col_if_missing("manager_name", "TEXT")
        await add_col_if_missing("gender", "TEXT")
        await add_col_if_missing("photo_thumb_path", "TEXT")
        await add_col_if_missing("teacher_user_id", "INTEGER")
        await add_col_if_missing("phone_last4", "TEXT")
        
        await db.commit()

        # 수업일지
        await db.execute("""
        CREATE TABLE IF NOT EXISTS class_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            meet_date TEXT NOT NULL,   -- YYYY-MM-DD
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
        )
        """)

        # 오디션
        await db.execute("""
        CREATE TABLE IF NOT EXISTS auditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            aud_date TEXT NOT NULL,   -- YYYY-MM-DD
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
        )
        """)

        # ✅ 연기영상(누적)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS acting_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            video_path TEXT NOT NULL,
            original_name TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
        )
        """)

        # 혹시 예전 오류(컬럼명 불일치)로 망가진 테이블이면 재생성
        cur = await db.execute("PRAGMA table_info(acting_videos)")
        vcols = [r[1] for r in await cur.fetchall()]
        if "video_path" not in vcols:
            await db.execute("DROP TABLE IF EXISTS acting_videos")
            await db.execute("""
            CREATE TABLE acting_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER NOT NULL,
                video_path TEXT NOT NULL,
                original_name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
            )
            """)

        # 캐스팅관리 기록(항목형)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS casting_management_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            meet_date TEXT NOT NULL,   -- YYYY-MM-DD
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
        )
        """)

        # 캐스팅 미팅 기록(항목형)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS casting_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            meet_date TEXT NOT NULL,  -- YYYY-MM-DD
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
        )
        """)

        # 첫 미팅 기록(항목형)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS first_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            meet_date TEXT NOT NULL,  -- YYYY-MM-DD
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
        )
        """)

                # users
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'staff', 'teacher')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """)

                # teacher_profiles
        await db.execute("""
        CREATE TABLE IF NOT EXISTS teacher_profiles (
            user_id INTEGER PRIMARY KEY,
            lesson_subject TEXT,
            lesson_days TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # teacher_lessons
        await db.execute("""
        CREATE TABLE IF NOT EXISTS teacher_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_user_id INTEGER NOT NULL,
            lesson_name TEXT,
            lesson_days TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(teacher_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS lesson_actor_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(lesson_id, actor_id),
            FOREIGN KEY(lesson_id) REFERENCES teacher_lessons(id) ON DELETE CASCADE,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,   -- YYYY-MM-DD
            status TEXT NOT NULL DEFAULT '미체크',   -- 출석 / 결석 / 지각 / 보강 / 미체크
            phone_input TEXT,
            feedback TEXT,
            checked_by_user_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(lesson_id, actor_id, attendance_date),
            FOREIGN KEY(lesson_id) REFERENCES teacher_lessons(id) ON DELETE CASCADE,
            FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE,
            FOREIGN KEY(checked_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_lesson_actor_assignments_lesson_id ON lesson_actor_assignments(lesson_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lesson_actor_assignments_actor_id ON lesson_actor_assignments(actor_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_class_logs_actor_id ON class_logs(actor_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_auditions_actor_id ON auditions(actor_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_acting_videos_actor_id ON acting_videos(actor_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_casting_management_logs_actor_id ON casting_management_logs(actor_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_casting_meetings_actor_id ON casting_meetings(actor_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_first_meetings_actor_id ON first_meetings(actor_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_actors_teacher_user_id ON actors(teacher_user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_attendance_logs_lesson_date ON attendance_logs(lesson_id, attendance_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_attendance_logs_actor_date ON attendance_logs(actor_id, attendance_date)")

        await db.commit()


async def migrate_legacy_log_tables():
    async with open_db() as db:

        async def get_columns(table_name: str):
            cur = await db.execute(f"PRAGMA table_info({table_name})")
            rows = await cur.fetchall()
            return [row["name"] for row in rows]

        # -----------------------------
        # class_logs: log_date -> meet_date
        # -----------------------------
        class_cols = await get_columns("class_logs")
        if class_cols and "meet_date" not in class_cols and "log_date" in class_cols:
            await db.execute("ALTER TABLE class_logs RENAME TO class_logs_old")

            await db.execute("""
                CREATE TABLE class_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id INTEGER NOT NULL,
                    meet_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                INSERT INTO class_logs (id, actor_id, meet_date, content, created_at)
                SELECT id, actor_id, log_date, content, created_at
                FROM class_logs_old
            """)

            await db.execute("DROP TABLE class_logs_old")

        # -----------------------------
        # casting_management_logs: log_date -> meet_date
        # -----------------------------
        cm_cols = await get_columns("casting_management_logs")
        if cm_cols and "meet_date" not in cm_cols and "log_date" in cm_cols:
            await db.execute("ALTER TABLE casting_management_logs RENAME TO casting_management_logs_old")

            await db.execute("""
                CREATE TABLE casting_management_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id INTEGER NOT NULL,
                    meet_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                INSERT INTO casting_management_logs (id, actor_id, meet_date, content, created_at)
                SELECT id, actor_id, log_date, content, created_at
                FROM casting_management_logs_old
            """)

            await db.execute("DROP TABLE casting_management_logs_old")

        # -----------------------------
        # casting_meetings: 혹시 예전 log_date면 교정
        # -----------------------------
        cmeet_cols = await get_columns("casting_meetings")
        if cmeet_cols and "meet_date" not in cmeet_cols and "log_date" in cmeet_cols:
            await db.execute("ALTER TABLE casting_meetings RENAME TO casting_meetings_old")

            await db.execute("""
                CREATE TABLE casting_meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id INTEGER NOT NULL,
                    meet_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                INSERT INTO casting_meetings (id, actor_id, meet_date, content, created_at)
                SELECT id, actor_id, log_date, content, created_at
                FROM casting_meetings_old
            """)

            await db.execute("DROP TABLE casting_meetings_old")

        # -----------------------------
        # first_meetings: 혹시 예전 log_date면 교정
        # -----------------------------
        first_cols = await get_columns("first_meetings")
        if first_cols and "meet_date" not in first_cols and "log_date" in first_cols:
            await db.execute("ALTER TABLE first_meetings RENAME TO first_meetings_old")

            await db.execute("""
                CREATE TABLE first_meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id INTEGER NOT NULL,
                    meet_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(actor_id) REFERENCES actors(id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                INSERT INTO first_meetings (id, actor_id, meet_date, content, created_at)
                SELECT id, actor_id, log_date, content, created_at
                FROM first_meetings_old
            """)

            await db.execute("DROP TABLE first_meetings_old")

        await db.commit()
