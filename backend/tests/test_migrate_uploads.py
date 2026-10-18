"""scripts/migrate_uploads_to_media.py 를 임시 DB와 임시 폴더로 확인한다."""
import importlib.util
import sqlite3
from pathlib import Path

from starlette.testclient import TestClient

SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "migrate_uploads_to_media.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("migrate_uploads_to_media", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrate_uploads(app, db_path, tmp_path):
    with TestClient(app):
        pass  # 스키마 생성

    legacy = tmp_path / "static_uploads"
    target = tmp_path / "storage_uploads"
    legacy.mkdir()
    (legacy / "photo_a.jpg").write_bytes(b"a")
    (legacy / "video_b.mp4").write_bytes(b"b")

    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO actors (name, photo_path, photo_thumb_path) VALUES ('배우', '/static/uploads/photo_a.jpg', '/media/uploads/already.jpg')")
    con.execute("INSERT INTO acting_videos (actor_id, video_path, created_at) VALUES (1, '/static/uploads/video_b.mp4', 'x')")
    con.commit()
    con.close()

    migrate = _load_script().migrate

    # 미리보기는 아무것도 바꾸지 않는다
    preview = migrate(str(db_path), legacy, target, apply=False)
    assert preview["files"] == 2
    assert preview["urls"]["actors.photo_path"] == 1
    assert preview["urls"]["acting_videos.video_path"] == 1
    assert (legacy / "photo_a.jpg").exists()

    result = migrate(str(db_path), legacy, target, apply=True)
    assert Path(result["backup"]).exists()
    assert (target / "photo_a.jpg").read_bytes() == b"a"
    assert not (legacy / "photo_a.jpg").exists()

    con = sqlite3.connect(db_path)
    assert con.execute("SELECT photo_path, photo_thumb_path FROM actors").fetchone() == (
        "/media/uploads/photo_a.jpg", "/media/uploads/already.jpg"
    )
    assert con.execute("SELECT video_path FROM acting_videos").fetchone() == ("/media/uploads/video_b.mp4",)
    con.close()

    # 다시 실행해도 바뀌는 것이 없다
    again = migrate(str(db_path), legacy, target, apply=False)
    assert again["files"] == 0 and sum(again["urls"].values()) == 0
