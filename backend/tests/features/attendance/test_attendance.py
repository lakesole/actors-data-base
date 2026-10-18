from datetime import datetime

from conftest import assert_denied, assert_login_alert


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def test_attendance_requires_login(client):
    assert_login_alert(client.get("/attendance"))


def test_attendance_page_for_teacher(seed):
    r = seed.teacher.get("/attendance")
    assert r.status_code == 200
    assert "연기반" in r.text
    assert "배정배우" in r.text


def test_attendance_page_teacher_cannot_open_other_lesson(seed):
    r = seed.teacher2.get(f"/attendance?lesson_id={seed.lesson_id}")
    assert r.status_code == 200
    assert "배정배우" not in r.text


def test_attendance_page_bad_date_falls_back_to_today(seed):
    r = seed.admin.get(f"/attendance?lesson_id={seed.lesson_id}&attendance_date=nope")
    assert r.status_code == 200
    assert _today() in r.text


def test_attendance_save_auto_check_and_feedback(seed, db):
    today = _today()
    a = seed.assigned
    data = {
        "lesson_id": str(seed.lesson_id),
        "attendance_date": today,
        f"phone_input_{a}": "1234",
        f"status_{a}": "",
        f"feedback_{a}": "발성 좋음",
    }
    r = seed.teacher.post("/attendance/save", data=data)
    assert r.status_code == 303
    assert r.headers["location"] == f"/attendance?lesson_id={seed.lesson_id}&attendance_date={today}"

    log = db("SELECT status, phone_input, feedback, checked_by_user_id FROM attendance_logs")[0]
    assert log == {
        "status": "출석",
        "phone_input": "1234",
        "feedback": "발성 좋음",
        "checked_by_user_id": seed.user_ids["teacher1"],
    }
    assert [r["content"] for r in db("SELECT content FROM class_logs")] == ["[연기반] 발성 좋음"]

    # 같은 날 같은 피드백은 수업일지에 중복 저장하지 않는다
    seed.teacher.post("/attendance/save", data=data)
    assert len(db("SELECT id FROM class_logs")) == 1
    assert len(db("SELECT id FROM attendance_logs")) == 1


def test_attendance_save_wrong_phone_is_unchecked(seed, db):
    a = seed.assigned
    seed.admin.post("/attendance/save", data={
        "lesson_id": str(seed.lesson_id),
        "attendance_date": _today(),
        f"phone_input_{a}": "0000",
    })
    assert db("SELECT status FROM attendance_logs")[0]["status"] == "미체크"


def test_attendance_save_explicit_status(seed, db):
    a = seed.assigned
    seed.admin.post("/attendance/save", data={
        "lesson_id": str(seed.lesson_id),
        "attendance_date": _today(),
        f"status_{a}": "지각",
    })
    assert db("SELECT status FROM attendance_logs")[0]["status"] == "지각"


def test_attendance_save_rejections(seed):
    assert_denied(seed.teacher2.post("/attendance/save", data={
        "lesson_id": str(seed.lesson_id), "attendance_date": _today(),
    }))
    assert_denied(seed.admin.post("/attendance/save", data={"lesson_id": "", "attendance_date": _today()}))
    assert_denied(seed.admin.post("/attendance/save", data={
        "lesson_id": str(seed.lesson_id), "attendance_date": "2024-02-30",
    }))


# ---------- 키오스크 ----------

def test_kiosk_requires_admin(seed):
    assert_denied(seed.staff.get("/attendance/kiosk"))
    assert_denied(seed.staff.post("/attendance/kiosk/check", data={"phone_last4": "1234"}))


def test_kiosk_page(seed):
    r = seed.admin.get("/attendance/kiosk")
    assert r.status_code == 200
    assert _today() in r.text


def test_kiosk_check_flow(seed, db):
    def check(value):
        return seed.admin.post("/attendance/kiosk/check", data={"phone_last4": value}).json()

    assert check("12") == {"ok": False, "message": "4자리를 입력해주세요."}
    assert check("9999") == {"ok": False, "message": "오늘 출석 대상자 중 일치하는 배우가 없습니다."}
    assert check("1234") == {"ok": True, "message": "배정배우 출석 완료", "actor_name": "배정배우", "status": "checked"}
    assert check("1234") == {"ok": True, "message": "배정배우 이미 출석 처리되었습니다.", "actor_name": "배정배우", "status": "already"}

    log = db("SELECT status, phone_input, checked_by_user_id FROM attendance_logs")[0]
    assert log == {"status": "출석", "phone_input": "1234", "checked_by_user_id": seed.user_ids["admin"]}


def test_kiosk_duplicate_phone(seed, db):
    db("UPDATE actors SET phone_last4='1234' WHERE id=?", (seed.other,))
    seed.admin.post(f"/admin/teachers/lesson/{seed.lesson_id}/actors/save",
                    data={"actor_ids": [str(seed.assigned), str(seed.other)]})
    body = seed.admin.post("/attendance/kiosk/check", data={"phone_last4": "1234"}).json()
    assert body["ok"] is False
    assert body["message"].startswith("번호가 중복됩니다. 관리자 확인 필요 (")


def test_kiosk_mode_locks_navigation(seed):
    seed.admin.get("/attendance/kiosk")

    r = seed.admin.get("/admin/users")
    assert r.status_code == 303
    assert r.headers["location"] == "/attendance/kiosk"

    assert seed.admin.get("/static/css/style.css").status_code == 200

    r = seed.admin.get("/attendance/kiosk/exit")
    assert r.status_code == 303
    assert r.headers["location"] == "/attendance"
    assert seed.admin.get("/admin/users").status_code == 200


def test_kiosk_mode_released_by_release_paths(seed):
    seed.admin.get("/attendance/kiosk")
    assert seed.admin.get("/").status_code == 200
    assert seed.admin.get("/admin/users").status_code == 200
