import io

from PIL import Image

from conftest import assert_denied


# ---------- 목록 / 검색 ----------

def test_index_lists_actors_for_anonymous(seed, client):
    r = client.get("/")
    assert r.status_code == 200
    assert "배정배우" in r.text
    assert "미배정배우" in r.text


def test_index_teacher_sees_only_assigned_actors(seed):
    r = seed.teacher.get("/")
    assert r.status_code == 200
    assert "배정배우" in r.text
    assert "미배정배우" not in r.text


def test_index_teacher_lesson_filter(seed):
    r = seed.teacher.get(f"/?lesson_id={seed.lesson_id}")
    assert "배정배우" in r.text


def test_index_filters(seed):
    r = seed.admin.get("/?gender=남자")
    assert "미배정배우" in r.text and "배정배우</" not in r.text.replace("미배정배우", "")

    r = seed.admin.get("/?q=미배정")
    assert "미배정배우" in r.text
    assert "배정배우" not in r.text.replace("미배정배우", "")

    r = seed.admin.get("/?height_group=180")
    assert "미배정배우" in r.text
    assert "배정배우" not in r.text.replace("미배정배우", "")

    r = seed.admin.get("/?birth_group=1990")
    assert "배정배우" in r.text
    assert "미배정배우" not in r.text


def test_index_ai_search(seed):
    r = seed.admin.get("/?ai_query=여자 승마 배우 찾아줘")
    assert r.status_code == 200
    assert "배정배우" in r.text
    assert "미배정배우" not in r.text


def test_index_status_filter(seed, db):
    db("UPDATE actors SET contract_end_date='2000-01-01' WHERE id=?", (seed.other,))
    r = seed.admin.get("/?status_filter=expired")
    assert "미배정배우" in r.text
    assert "배정배우" not in r.text.replace("미배정배우", "")

    r = seed.admin.get("/?status_filter=active")
    assert "배정배우" in r.text
    assert "미배정배우" not in r.text


def test_index_list_view_and_paging(seed):
    r = seed.admin.get("/?view=list&page=1&per_page=1")
    assert r.status_code == 200


# ---------- 생성 ----------

def test_create_actor_requires_admin_or_staff(seed):
    assert_denied(seed.teacher.get("/actors/new"))
    assert_denied(seed.teacher.post("/actors/new", data={"name": "x"}))


def test_create_actor_page(seed):
    r = seed.staff.get("/actors/new")
    assert r.status_code == 200
    assert "teacher1" in r.text


def test_create_actor_cleans_values(seed, db):
    r = seed.staff.post("/actors/new", data={
        "name": "  신규배우 ",
        "birth_year": "1999년",
        "height_cm": "abc",
        "weight_kg": "55.5",
        "contract_date": "2024-03-01",
        "phone_last4": "010-1234-9999",
        "teacher_user_id": str(seed.user_ids["teacher1"]),
    })
    assert r.status_code == 303
    actor_id = int(r.headers["location"].rsplit("/", 1)[1])
    row = db("SELECT * FROM actors WHERE id=?", (actor_id,))[0]
    assert row["name"] == "신규배우"
    assert row["birth_year"] == 1999
    assert row["height_cm"] is None
    assert row["weight_kg"] == 55.5
    assert row["contract_end_date"] == "2025-02-28"
    assert row["phone_last4"] == "0101"
    assert row["teacher_user_id"] == seed.user_ids["teacher1"]


def _jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (1200, 800), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_create_actor_with_photo_and_video(seed, db, upload_dir, client):
    r = seed.staff.post(
        "/actors/new",
        data={"name": "사진배우"},
        files=[
            ("photo", ("face.png", _jpeg_bytes(), "image/png")),
            ("acting_videos", ("a.mp4", b"video-a", "video/mp4")),
            ("acting_videos", ("b.mp4", b"video-b", "video/mp4")),
        ],
    )
    assert r.status_code == 303
    actor_id = int(r.headers["location"].rsplit("/", 1)[1])
    row = db("SELECT photo_path, photo_thumb_path FROM actors WHERE id=?", (actor_id,))[0]
    # Phase 4부터 업로드 파일은 storage/uploads에 저장되고 /media/uploads로 서빙된다
    assert row["photo_path"].startswith("/media/uploads/photo_") and row["photo_path"].endswith(".jpg")
    assert row["photo_thumb_path"].startswith("/media/uploads/photo_thumb_")
    with Image.open(upload_dir / row["photo_path"].removeprefix("/media/uploads/")) as img:
        assert max(img.size) == 1000
    assert client.get(row["photo_path"]).status_code == 200

    # 현재는 여러 개를 올려도 마지막 1개만 저장된다 (docs/found-issues.md #13)
    videos = db("SELECT original_name FROM acting_videos WHERE actor_id=? ORDER BY id", (actor_id,))
    assert [v["original_name"] for v in videos] == ["b.mp4"]


# ---------- 상세 ----------

def test_detail_access(seed, client):
    assert client.get(f"/actors/{seed.assigned}").status_code == 200
    assert seed.teacher.get(f"/actors/{seed.assigned}").status_code == 200
    assert_denied(seed.teacher.get(f"/actors/{seed.other}"))


def test_detail_missing_actor_redirects_home(seed):
    r = seed.admin.get("/actors/9999")
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_detail_tabs(seed):
    for tab in ["compcard", "classlog", "auditions", "video", "casting_management", "casting_meetings", "first_meeting"]:
        assert seed.admin.get(f"/actors/{seed.assigned}?tab={tab}").status_code == 200


# ---------- 수정 ----------

def test_edit_requires_admin_or_staff(seed):
    assert_denied(seed.teacher.get(f"/actors/{seed.assigned}/edit"))
    assert_denied(seed.teacher.post(f"/actors/{seed.assigned}/edit", data={"name": "x"}))


def test_edit_page(seed):
    r = seed.staff.get(f"/actors/{seed.assigned}/edit")
    assert r.status_code == 200
    assert "배정배우" in r.text
    assert_denied(seed.staff.get("/actors/9999/edit"))


def test_edit_actor_updates_and_keeps_phone(seed, db):
    r = seed.staff.post(f"/actors/{seed.assigned}/edit", data={
        "name": "수정된배우",
        "phone_last4": "",
        "q": "검색어",
        "page": "2",
    })
    assert r.status_code == 303
    assert r.headers["location"].startswith(f"/actors/{seed.assigned}?q=%EA%B2%80%EC%83%89%EC%96%B4&m=")
    assert "&page=2&per_page=20&" in r.headers["location"]
    row = db("SELECT name, phone_last4, hobby FROM actors WHERE id=?", (seed.assigned,))[0]
    assert row == {"name": "수정된배우", "phone_last4": "1234", "hobby": ""}


def test_edit_missing_actor(seed):
    assert_denied(seed.staff.post("/actors/9999/edit", data={"name": "x"}))


# ---------- 삭제 ----------

def test_delete_actor_by_admin(seed, db):
    r = seed.admin.post(f"/actors/{seed.other}/delete")
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert not db("SELECT id FROM actors WHERE id=?", (seed.other,))


def test_delete_actor_by_assigned_teacher_is_allowed(seed, db):
    """현재 동작 기록용. 담당 teacher도 배우를 삭제할 수 있다 (docs/found-issues.md 참고)."""
    r = seed.teacher.post(f"/actors/{seed.assigned}/delete")
    assert r.status_code == 303
    assert not db("SELECT id FROM actors WHERE id=?", (seed.assigned,))


def test_delete_actor_by_unassigned_teacher_denied(seed, db):
    assert_denied(seed.teacher2.post(f"/actors/{seed.assigned}/delete"))
    assert db("SELECT id FROM actors WHERE id=?", (seed.assigned,))


def test_delete_video(seed, db):
    db("INSERT INTO acting_videos (actor_id, video_path, original_name, created_at) VALUES (?, ?, ?, ?)",
       (seed.assigned, "/media/uploads/none.mp4", "none.mp4", "2024-01-01T00:00:00"))
    video_id = db("SELECT id FROM acting_videos")[0]["id"]

    assert_denied(seed.teacher.post(f"/actors/{seed.assigned}/videos/{video_id}/delete"))

    r = seed.staff.post(f"/actors/{seed.assigned}/videos/{video_id}/delete")
    assert r.status_code == 303
    assert r.headers["location"] == f"/actors/{seed.assigned}?tab=video"
    assert not db("SELECT id FROM acting_videos")
