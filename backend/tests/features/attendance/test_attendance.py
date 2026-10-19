from datetime import datetime


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def test_get_attendance(seed, client):
    assert client.get("/api/attendance").status_code == 401

    body = seed.teacher.get("/api/attendance").json()
    assert body["lesson_id"] == str(seed.lesson_id)
    assert body["attendance_date"] == _today()
    assert body["selected_lesson"]["lesson_name"] == "연기반"
    assert [a["name"] for a in body["actors"]] == ["배정배우"]

    body = seed.teacher2.get(f"/api/attendance?lesson_id={seed.lesson_id}").json()
    assert body["selected_lesson"] is None and body["actors"] == []


def test_save_attendance(seed, db):
    body = {
        "lesson_id": seed.lesson_id,
        "attendance_date": _today(),
        "entries": [{"actor_id": seed.assigned, "phone_input": "1234", "feedback": "발성 좋음"}],
    }
    assert seed.teacher.put("/api/attendance", json=body).status_code == 204
    log = db("SELECT status, phone_input, feedback FROM attendance_logs")[0]
    assert log == {"status": "출석", "phone_input": "1234", "feedback": "발성 좋음"}
    assert [r["content"] for r in db("SELECT content FROM class_logs")] == ["[연기반] 발성 좋음"]

    actors = seed.teacher.get("/api/attendance").json()["actors"]
    assert actors[0]["status"] == "출석"

    r = seed.teacher2.put("/api/attendance", json=body)
    assert r.status_code == 403 and r.json()["detail"] == "해당 수업 접근 권한이 없습니다."

    r = seed.teacher.put("/api/attendance", json={**body, "attendance_date": "2024-02-30"})
    assert r.status_code == 400


def test_kiosk(seed, db):
    assert seed.staff.get("/api/attendance/kiosk").status_code == 403

    info = seed.admin.get("/api/attendance/kiosk").json()
    assert info["today_str"] == _today() and info["today_candidates_count"] == 1

    # 키오스크 모드에서는 키오스크/인증 API 외에는 막힌다
    r = seed.admin.get("/api/users")
    assert r.status_code == 403 and r.json()["code"] == "KIOSK_MODE"

    def check(value):
        return seed.admin.post("/api/attendance/kiosk/check", json={"phone_last4": value}).json()

    assert check("12") == {"ok": False, "message": "4자리를 입력해주세요.", "actor_name": None, "status": None}
    assert check("1234")["status"] == "checked"
    assert check("1234")["status"] == "already"

    assert seed.admin.post("/api/attendance/kiosk/exit").status_code == 204
    assert seed.admin.get("/api/users").status_code == 200


def _save(client, seed, entries, date=None):
    return client.put("/api/attendance", json={
        "lesson_id": seed.lesson_id, "attendance_date": date or _today(), "entries": entries,
    })


def test_attendance_bad_date_falls_back_to_today(seed):
    body = seed.admin.get(f"/api/attendance?lesson_id={seed.lesson_id}&attendance_date=nope").json()
    assert body["attendance_date"] == _today()


def test_save_dedupes_class_log_and_rows(seed, db):
    entries = [{"actor_id": seed.assigned, "phone_input": "1234", "feedback": "발성 좋음"}]
    assert _save(seed.teacher, seed, entries).status_code == 204
    assert _save(seed.teacher, seed, entries).status_code == 204
    assert len(db("SELECT id FROM class_logs")) == 1
    assert len(db("SELECT id FROM attendance_logs")) == 1
    log = db("SELECT checked_by_user_id FROM attendance_logs")[0]
    assert log["checked_by_user_id"] == seed.user_ids["teacher1"]


def test_save_wrong_phone_is_unchecked(seed, db):
    _save(seed.admin, seed, [{"actor_id": seed.assigned, "phone_input": "0000"}])
    assert db("SELECT status FROM attendance_logs")[0]["status"] == "미체크"


def test_save_explicit_status(seed, db):
    _save(seed.admin, seed, [{"actor_id": seed.assigned, "status": "지각"}])
    assert db("SELECT status FROM attendance_logs")[0]["status"] == "지각"


def test_save_requires_login(seed, client):
    assert _save(client, seed, []).status_code == 401


def test_kiosk_duplicate_phone(seed, db):
    db("UPDATE actors SET phone_last4='1234' WHERE id=?", (seed.other,))
    seed.admin.put(f"/api/teachers/lessons/{seed.lesson_id}/actors", json={"actor_ids": [seed.assigned, seed.other]})
    body = seed.admin.post("/api/attendance/kiosk/check", json={"phone_last4": "1234"}).json()
    assert body["ok"] is False
    assert body["message"].startswith("번호가 중복됩니다. 관리자 확인 필요 (")


def test_kiosk_check_flow(seed, db):
    def check(value):
        return seed.admin.post("/api/attendance/kiosk/check", json={"phone_last4": value}).json()

    assert check("9999")["message"] == "오늘 출석 대상자 중 일치하는 배우가 없습니다."
    assert check("1234") == {"ok": True, "message": "배정배우 출석 완료", "actor_name": "배정배우", "status": "checked"}
    assert check("1234")["message"] == "배정배우 이미 출석 처리되었습니다."
    log = db("SELECT status, phone_input, checked_by_user_id FROM attendance_logs")[0]
    assert log == {"status": "출석", "phone_input": "1234", "checked_by_user_id": seed.user_ids["admin"]}
    assert seed.staff.post("/api/attendance/kiosk/check", json={"phone_last4": "1234"}).status_code == 403


def test_kiosk_mode_is_released_by_list_and_attendance_get(seed):
    for path in ["/api/actors", "/api/attendance"]:
        seed.admin.get("/api/attendance/kiosk")
        assert seed.admin.get("/api/users").status_code == 403
        assert seed.admin.get(path).status_code == 200
        assert seed.admin.get("/api/users").status_code == 200


def test_kiosk_mode_is_not_released_by_writes(seed):
    seed.admin.get("/api/attendance/kiosk")
    r = seed.admin.post("/api/actors", data={"name": "키오스크중"})
    assert r.status_code == 403 and r.json()["code"] == "KIOSK_MODE"
    assert seed.admin.get("/api/users").status_code == 403
    assert seed.admin.get("/media/uploads/none.jpg").status_code == 404   # 미디어는 막지 않는다
