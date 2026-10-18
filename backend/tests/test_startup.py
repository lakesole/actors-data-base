"""앱 시작 시 실행되는 스키마 마이그레이션과 데이터 정리를 기존 데이터가 있는 DB로 확인한다."""
import sqlite3

from starlette.testclient import TestClient


def _start(app):
    with TestClient(app):
        pass


def test_startup_normalizes_existing_actor_data(app, db_path):
    _start(app)

    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT INTO actors (name, birth_year, contract_date, contract_end_date)
        VALUES ('기존배우', '1990년생', '2024-03-01 10:00', '')
    """)
    con.commit()
    con.close()

    _start(app)

    con = sqlite3.connect(db_path)
    row = con.execute("SELECT birth_year, contract_date, contract_end_date FROM actors").fetchone()
    con.close()
    assert row == (1990, "2024-03-01", "2025-02-28")


def test_startup_migrates_legacy_log_date_columns(app, db_path):
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE class_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    con.execute("INSERT INTO class_logs (actor_id, log_date, content, created_at) VALUES (1, '2024-01-01', '예전 기록', 'x')")
    con.commit()
    con.close()

    _start(app)

    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT meet_date, content FROM class_logs").fetchall()
    con.close()
    assert rows == [("2024-01-01", "예전 기록")]


def test_startup_creates_default_admin_once(app, db_path, login_as):
    _start(app)
    con = sqlite3.connect(db_path)
    assert con.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone() == (1,)
    con.close()
    login_as("admin", "1234")
