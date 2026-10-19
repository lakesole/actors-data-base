"""
특성 테스트(characterization test) 공통 fixture.

리팩터링 전후에 같은 테스트가 통과하는지로 동작 보존을 확인한다.
앱을 불러오는 방법(load_app)만 단계별로 바뀌고, 테스트 본문은 바뀌지 않아야 한다.
"""
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from passlib.context import CryptContext
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALL_DAYS = "월,화,수,목,금,토,일"
PASSWORD = "pass1234"


def load_app(workdir: Path):
    # 설정은 import 시점에 환경변수에서 읽으므로 import 전에 지정한다.
    os.environ["STORAGE_DIR"] = str(workdir / "storage")
    os.environ["DB_PATH"] = str(workdir / "actors.db")
    os.environ["SECRET_KEY"] = "test-secret"
    sys.path.insert(0, str(BACKEND_DIR))

    from app.core import security
    # 테스트 속도용: bcrypt 비용만 낮춘다 (해시 형식은 동일)
    security.pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=4)

    from app.main import app
    return app


@pytest.fixture(scope="session")
def workdir(tmp_path_factory):
    return tmp_path_factory.mktemp("app")


@pytest.fixture(scope="session")
def app(workdir):
    return load_app(workdir)


@pytest.fixture
def upload_dir(workdir):
    return workdir / "storage" / "uploads"


@pytest.fixture
def db_path(workdir):
    path = workdir / "actors.db"
    if path.exists():
        path.unlink()
    return path


@pytest.fixture
def client(app, db_path):
    """로그인하지 않은 클라이언트. 컨텍스트 진입 시 startup이 실행되어 새 DB가 만들어진다."""
    with TestClient(app, raise_server_exceptions=False, follow_redirects=False) as c:
        yield c


@pytest.fixture
def login_as(app, client):
    def _login(username: str, password: str = PASSWORD) -> TestClient:
        c = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
        r = c.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text[:300]
        return c
    return _login


@pytest.fixture
def db(db_path, client):
    def query(sql: str, params=()):
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in con.execute(sql, params).fetchall()]
            con.commit()
            return rows
        finally:
            con.close()
    return query


@pytest.fixture
def seed(login_as, db):
    """
    admin(기본 계정), staff1, teacher1, teacher2 계정과
    teacher1의 수업(연기반, 매일)에 배정된 배우 1명, 미배정 배우 1명을 만든다.
    """
    admin = login_as("admin", "1234")

    for username, role in [("staff1", "staff"), ("teacher1", "teacher"), ("teacher2", "teacher")]:
        r = admin.post("/api/users", json={
            "username": username,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "display_name": username,
            "role": role,
        })
        assert r.status_code == 201, r.text[:300]

    user_ids = {row["username"]: row["id"] for row in db("SELECT id, username FROM users")}

    def create_actor(**fields) -> int:
        r = admin.post("/api/actors", data=fields)
        assert r.status_code == 201, r.text[:300]
        return r.json()["id"]

    assigned = create_actor(
        name="배정배우", gender="여자", birth_year="1995", height_cm="165",
        hobby="승마", phone_last4="1234",
    )
    other = create_actor(
        name="미배정배우", gender="남자", birth_year="1988", height_cm="182",
        phone_last4="5678",
    )

    r = admin.post(f"/api/teachers/{user_ids['teacher1']}/lessons",
                   json={"lesson_name": "연기반", "lesson_days": ALL_DAYS})
    assert r.status_code == 201, r.text[:300]
    lesson_id = r.json()["id"]
    r = admin.put(f"/api/teachers/lessons/{lesson_id}/actors", json={"actor_ids": [assigned]})
    assert r.status_code == 204, r.text[:300]

    return SimpleNamespace(
        admin=admin,
        staff=login_as("staff1"),
        teacher=login_as("teacher1"),
        teacher2=login_as("teacher2"),
        user_ids=user_ids,
        assigned=assigned,
        other=other,
        lesson_id=lesson_id,
        create_actor=create_actor,
    )


def assert_denied(r):
    """거부된 요청(401/403)인지 확인한다."""
    assert r.status_code in (401, 403), (r.status_code, r.text[:300])
