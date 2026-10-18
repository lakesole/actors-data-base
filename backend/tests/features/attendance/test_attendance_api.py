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
