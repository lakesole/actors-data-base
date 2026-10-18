import pytest

from conftest import assert_denied

# (URL 경로, 테이블, 날짜 컬럼/폼 필드, 상세 화면 탭)
RECORD_TYPES = [
    ("classlogs", "class_logs", "meet_date", "classlog"),
    ("auditions", "auditions", "aud_date", "auditions"),
    ("casting-management", "casting_management_logs", "meet_date", "casting_management"),
    ("casting-meetings", "casting_meetings", "meet_date", "casting_meetings"),
    ("first-meetings", "first_meetings", "meet_date", "first_meeting"),
]


@pytest.fixture(params=RECORD_TYPES, ids=[t[0] for t in RECORD_TYPES])
def record_type(request):
    return request.param


def test_record_crud(seed, db, record_type):
    path, table, date_field, tab = record_type
    actor = seed.assigned
    base = f"/actors/{actor}/{path}"
    tab_url = f"/actors/{actor}?tab={tab}"

    assert seed.staff.get(f"{base}/new").status_code == 200

    r = seed.staff.post(f"{base}/new", data={date_field: "2024-05-01", "content": "첫 기록"})
    assert r.status_code == 303
    assert r.headers["location"] == tab_url
    item_id = db(f"SELECT id FROM {table}")[0]["id"]

    r = seed.staff.get(f"{base}/{item_id}/edit")
    assert r.status_code == 200
    assert "첫 기록" in r.text

    r = seed.staff.post(f"{base}/{item_id}/edit", data={date_field: "2024-06-01", "content": "수정 기록"})
    assert r.status_code == 303
    assert r.headers["location"] == tab_url
    row = db(f"SELECT {date_field}, content FROM {table} WHERE id=?", (item_id,))[0]
    assert row == {date_field: "2024-06-01", "content": "수정 기록"}

    assert "수정 기록" in seed.staff.get(tab_url).text

    r = seed.staff.post(f"{base}/{item_id}/delete")
    assert r.status_code == 303
    assert r.headers["location"] == tab_url
    assert not db(f"SELECT id FROM {table}")


def test_edit_missing_record_redirects_to_tab(seed, record_type):
    path, _, _, tab = record_type
    r = seed.staff.get(f"/actors/{seed.assigned}/{path}/9999/edit")
    assert r.status_code == 303
    assert r.headers["location"] == f"/actors/{seed.assigned}?tab={tab}"


def test_teacher_permissions(seed, db, record_type):
    path, table, date_field, _ = record_type
    data = {date_field: "2024-05-01", "content": "선생님 기록"}

    assert seed.teacher.post(f"/actors/{seed.assigned}/{path}/new", data=data).status_code == 303
    assert_denied(seed.teacher.post(f"/actors/{seed.other}/{path}/new", data=data))
    assert_denied(seed.teacher.get(f"/actors/{seed.other}/{path}/new"))

    item_id = db(f"SELECT id FROM {table}")[0]["id"]
    assert_denied(seed.teacher.post(f"/actors/{seed.assigned}/{path}/{item_id}/delete"))
    assert db(f"SELECT id FROM {table}")


def test_anonymous_is_rejected(client, seed, record_type):
    path, _, date_field, _ = record_type
    r = client.post(f"/actors/{seed.assigned}/{path}/new", data={date_field: "2024-05-01", "content": "x"})
    assert "로그인이 필요합니다." in r.text


@pytest.mark.parametrize("bad_date", ["2024-13-01", "99-01-01", "1899-12-31"])
def test_invalid_date_rejected(seed, db, record_type, bad_date):
    path, table, date_field, _ = record_type
    r = seed.staff.post(f"/actors/{seed.assigned}/{path}/new", data={date_field: bad_date, "content": "x"})
    assert_denied(r)
    assert not db(f"SELECT id FROM {table}")
