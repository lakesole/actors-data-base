import pytest

from conftest import PASSWORD, assert_denied


def test_admin_page_requires_admin(seed):
    assert_denied(seed.staff.get("/admin/users"))
    assert_denied(seed.teacher.get("/admin/users"))


def test_admin_page_lists_users(seed):
    r = seed.admin.get("/admin/users")
    assert r.status_code == 200
    for username in ["staff1", "teacher1", "teacher2"]:
        assert username in r.text


@pytest.mark.parametrize("override, message", [
    ({"display_name": "   "}, "아이디, 비밀번호, 이름은 필수입니다."),
    ({"username": "abc"}, "아이디는 4자 이상으로 입력해주세요."),
    ({"password": "abc", "password_confirm": "abc"}, "비밀번호는 4자 이상으로 입력해주세요."),
    ({"password_confirm": "different"}, "비밀번호 확인이 일치하지 않습니다."),
    ({"role": "owner"}, "권한 값이 올바르지 않습니다."),
    ({"username": "staff1"}, "이미 사용 중인 아이디입니다."),
])
def test_create_user_validation(seed, override, message):
    data = {
        "username": "newuser",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        "display_name": "새 사용자",
        "role": "staff",
        **override,
    }
    r = seed.admin.post("/admin/users/new", data=data)
    assert r.status_code == 200
    assert message in r.text


def test_create_user_with_empty_field_is_422(seed):
    """빈 문자열은 FastAPI 폼 검증에서 먼저 걸려 422가 된다."""
    r = seed.admin.post("/admin/users/new", data={
        "username": "newuser", "password": PASSWORD, "password_confirm": PASSWORD,
        "display_name": "", "role": "staff",
    })
    assert r.status_code == 422


def test_create_user_requires_admin(seed):
    r = seed.staff.post("/admin/users/new", data={
        "username": "hacker", "password": PASSWORD, "password_confirm": PASSWORD,
        "display_name": "x", "role": "admin",
    })
    assert_denied(r)


def test_creating_teacher_creates_profile(seed, db):
    rows = db("SELECT user_id FROM teacher_profiles")
    assert {r["user_id"] for r in rows} == {seed.user_ids["teacher1"], seed.user_ids["teacher2"]}


def test_toggle_active(seed, db):
    staff_id = seed.user_ids["staff1"]
    r = seed.admin.post(f"/admin/users/{staff_id}/toggle-active")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/users?success=toggled"
    assert db("SELECT is_active FROM users WHERE id=?", (staff_id,))[0]["is_active"] == 0

    seed.admin.post(f"/admin/users/{staff_id}/toggle-active")
    assert db("SELECT is_active FROM users WHERE id=?", (staff_id,))[0]["is_active"] == 1


def test_cannot_toggle_self(seed):
    assert_denied(seed.admin.post(f"/admin/users/{seed.user_ids['admin']}/toggle-active"))


def test_toggle_missing_user(seed):
    assert_denied(seed.admin.post("/admin/users/9999/toggle-active"))


def test_change_role_to_teacher_creates_profile(seed, db):
    staff_id = seed.user_ids["staff1"]
    r = seed.admin.post(f"/admin/users/{staff_id}/change-role", data={"role": "teacher"})
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/users?success=role_changed"
    assert db("SELECT role FROM users WHERE id=?", (staff_id,))[0]["role"] == "teacher"
    assert db("SELECT user_id FROM teacher_profiles WHERE user_id=?", (staff_id,))


def test_change_role_validation(seed):
    r = seed.admin.post(f"/admin/users/{seed.user_ids['staff1']}/change-role", data={"role": "owner"})
    assert "권한 값이 올바르지 않습니다." in r.text

    r = seed.admin.post(f"/admin/users/{seed.user_ids['admin']}/change-role", data={"role": "staff"})
    assert "현재 로그인한 본인 계정의 권한은 변경할 수 없습니다." in r.text

    assert_denied(seed.admin.post("/admin/users/9999/change-role", data={"role": "staff"}))


def test_reset_password(seed, login_as):
    teacher2_id = seed.user_ids["teacher2"]

    r = seed.admin.post(f"/admin/users/{teacher2_id}/reset-password",
                        data={"new_password": "abc", "new_password_confirm": "abc"})
    assert "비밀번호는 4자 이상으로 입력해주세요." in r.text

    r = seed.admin.post(f"/admin/users/{teacher2_id}/reset-password",
                        data={"new_password": "reset1", "new_password_confirm": "reset2"})
    assert "비밀번호 확인이 일치하지 않습니다." in r.text

    r = seed.admin.post(f"/admin/users/{teacher2_id}/reset-password",
                        data={"new_password": "reset1", "new_password_confirm": "reset1"})
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/users?success=pw_reset_teacher2"
    login_as("teacher2", "reset1")


def test_delete_user(seed, db):
    staff_id = seed.user_ids["staff1"]
    r = seed.admin.post(f"/admin/users/{staff_id}/delete")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/users?success=deleted"
    assert not db("SELECT id FROM users WHERE id=?", (staff_id,))


def test_cannot_delete_self_or_missing(seed):
    assert_denied(seed.admin.post(f"/admin/users/{seed.user_ids['admin']}/delete"))
    assert_denied(seed.admin.post("/admin/users/9999/delete"))
