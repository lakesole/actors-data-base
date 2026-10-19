import pytest

# (API 경로, 테이블)
API_TYPES = [
    ("class-logs", "class_logs"),
    ("auditions", "auditions"),
    ("casting-management", "casting_management_logs"),
    ("casting-meetings", "casting_meetings"),
    ("first-meetings", "first_meetings"),
]


@pytest.fixture(params=API_TYPES, ids=[t[0] for t in API_TYPES])
def api_type(request):
    return request.param


def test_crud(seed, db, api_type):
    path, table = api_type
    base = f"/api/actors/{seed.assigned}/{path}"

    r = seed.staff.post(base, json={"date": "2024-05-01", "content": "첫 기록"})
    assert r.status_code == 201
    item = r.json()
    assert item["date"] == "2024-05-01" and item["content"] == "첫 기록"

    assert [x["content"] for x in seed.staff.get(base).json()] == ["첫 기록"]
    assert seed.staff.get(f"{base}/{item['id']}").json()["content"] == "첫 기록"

    r = seed.staff.patch(f"{base}/{item['id']}", json={"date": "2024-06-01", "content": "수정"})
    assert r.status_code == 200 and r.json()["date"] == "2024-06-01"

    assert seed.staff.delete(f"{base}/{item['id']}").status_code == 204
    assert not db(f"SELECT id FROM {table}")
    assert seed.staff.get(f"{base}/{item['id']}").status_code == 404


def test_validation_and_permissions(seed, db, client, api_type):
    path, table = api_type
    base = f"/api/actors/{seed.assigned}/{path}"

    r = seed.staff.post(base, json={"date": "2024-13-01", "content": "x"})
    assert r.status_code == 400
    assert r.json()["detail"] == "올바른 날짜가 아닙니다."

    assert client.post(base, json={"date": "2024-05-01", "content": "x"}).status_code == 401
    assert seed.teacher.post(f"/api/actors/{seed.other}/{path}", json={"date": "2024-05-01", "content": "x"}).status_code == 403

    r = seed.teacher.post(base, json={"date": "2024-05-01", "content": "선생님 기록"})
    assert r.status_code == 201
    assert seed.teacher.delete(f"{base}/{r.json()['id']}").status_code == 403


def test_teacher_can_list_only_class_logs(seed, api_type):
    path, _ = api_type
    r = seed.teacher.get(f"/api/actors/{seed.assigned}/{path}")
    assert r.status_code == (200 if path == "class-logs" else 403)


def test_edit_missing_record_is_404(seed, api_type):
    path, _ = api_type
    assert seed.staff.patch(f"/api/actors/{seed.assigned}/{path}/9999", json={"date": "2024-05-01", "content": "x"}).status_code == 404
    # 없는 기록을 지워도 에러가 아니다 (기존 동작)
    assert seed.staff.delete(f"/api/actors/{seed.assigned}/{path}/9999").status_code == 204


@pytest.mark.parametrize("bad_date", ["2024-13-01", "99-01-01", "1899-12-31"])
def test_invalid_date_rejected(seed, db, api_type, bad_date):
    path, table = api_type
    r = seed.staff.post(f"/api/actors/{seed.assigned}/{path}", json={"date": bad_date, "content": "x"})
    assert r.status_code == 400
    assert not db(f"SELECT id FROM {table}")
