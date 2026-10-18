import io

from PIL import Image


def _names(r):
    return [a["name"] for a in r.json()["items"]]


def test_list_for_anonymous_and_teacher(seed, client):
    r = client.get("/api/actors")
    assert r.status_code == 200
    assert set(_names(r)) == {"배정배우", "미배정배우"}
    assert r.json()["total_count"] == 2

    r = seed.teacher.get("/api/actors")
    assert _names(r) == ["배정배우"]
    assert r.json()["teacher_lessons"][0]["lesson_name"] == "연기반"


def test_list_filters_and_ai(seed, db):
    assert _names(seed.admin.get("/api/actors?gender=남자")) == ["미배정배우"]
    assert _names(seed.admin.get("/api/actors?height_group=180")) == ["미배정배우"]
    assert _names(seed.admin.get("/api/actors?birth_group=1990")) == ["배정배우"]

    r = seed.admin.get("/api/actors", params={"ai_query": "여자 승마"})
    body = r.json()
    assert _names(r) == ["배정배우"]
    assert body["ai_parsed"]["gender"] == "여자"
    assert body["items"][0]["ai_score"] > 0
    assert "승마" in body["items"][0]["ai_matched"]

    db("UPDATE actors SET contract_end_date='2000-01-01' WHERE id=?", (seed.other,))
    r = seed.admin.get("/api/actors?status_filter=expired")
    assert _names(r) == ["미배정배우"]
    assert r.json()["items"][0]["contract_status"] == "expired"


def test_paging(seed):
    body = seed.admin.get("/api/actors?per_page=1&page=2").json()
    assert body["total_pages"] == 2 and body["page"] == 2 and len(body["items"]) == 1


def test_detail(seed, client):
    r = client.get(f"/api/actors/{seed.assigned}")
    assert r.status_code == 200
    assert r.json()["name"] == "배정배우"
    assert r.json()["contract_status_label"] == "활동중"

    assert seed.teacher.get(f"/api/actors/{seed.assigned}").status_code == 200
    r = seed.teacher.get(f"/api/actors/{seed.other}")
    assert r.status_code == 403 and r.json()["detail"] == "담당 배우만 볼 수 있습니다."
    assert client.get("/api/actors/9999").status_code == 404


def test_simple_list(seed):
    assert seed.staff.get("/api/actors/simple").json() == [
        {"id": seed.other, "name": "미배정배우"},
        {"id": seed.assigned, "name": "배정배우"},
    ]
    assert seed.teacher.get("/api/actors/simple").status_code == 403


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), "blue").save(buf, format="PNG")
    return buf.getvalue()


def test_create_update_delete(seed, db, client):
    r = seed.teacher.post("/api/actors", data={"name": "x"})
    assert r.status_code == 403 and r.json()["detail"] == "배우 등록 권한이 없습니다."

    r = seed.staff.post(
        "/api/actors",
        data={"name": "API배우", "gender": "여자", "contract_date": "2024-03-01", "phone_last4": "4321"},
        files=[("photo", ("p.png", _png(), "image/png"))],
    )
    assert r.status_code == 201
    actor_id = r.json()["id"]
    actor = client.get(f"/api/actors/{actor_id}").json()
    assert actor["contract_end_date"] == "2025-02-28"
    assert actor["photo_path"].startswith("/media/uploads/")
    assert client.get(actor["photo_path"]).status_code == 200

    r = seed.staff.patch(f"/api/actors/{actor_id}", data={"name": "API배우2", "gender": "여자", "phone_last4": ""})
    assert r.status_code == 200
    assert r.json()["name"] == "API배우2"
    assert r.json()["phone_last4"] == "4321"
    assert r.json()["photo_path"] == actor["photo_path"]
    assert seed.teacher.patch(f"/api/actors/{actor_id}", data={"name": "x"}).status_code == 403

    assert seed.teacher2.delete(f"/api/actors/{actor_id}").status_code == 403
    assert seed.admin.delete(f"/api/actors/{actor_id}").status_code == 204
    assert client.get(f"/api/actors/{actor_id}").status_code == 404


def test_videos(seed, db):
    db("INSERT INTO acting_videos (actor_id, video_path, original_name, created_at) VALUES (?, ?, ?, ?)",
       (seed.assigned, "/media/uploads/v.mp4", "v.mp4", "2024-01-01T00:00:00"))
    videos = seed.staff.get(f"/api/actors/{seed.assigned}/videos").json()
    assert [v["original_name"] for v in videos] == ["v.mp4"]

    # teacher는 담당 배우라도 수업일지 외의 탭은 볼 수 없다
    assert seed.teacher.get(f"/api/actors/{seed.assigned}/videos").status_code == 403

    video_id = videos[0]["id"]
    assert seed.teacher.delete(f"/api/actors/{seed.assigned}/videos/{video_id}").status_code == 403
    assert seed.staff.delete(f"/api/actors/{seed.assigned}/videos/{video_id}").status_code == 204
    assert not db("SELECT id FROM acting_videos")
