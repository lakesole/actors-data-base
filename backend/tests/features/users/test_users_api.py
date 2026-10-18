from conftest import PASSWORD


def test_requires_admin(seed, client):
    assert client.get("/api/users").status_code == 401
    r = seed.staff.get("/api/users")
    assert r.status_code == 403
    assert r.json() == {"detail": "관리자 권한이 필요합니다.", "code": "FORBIDDEN"}


def test_list_users(seed):
    users = seed.admin.get("/api/users").json()
    assert [u["username"] for u in users][0] == "admin"
    assert {u["username"] for u in users} == {"admin", "staff1", "teacher1", "teacher2"}
    assert users[0]["is_active"] is True


def test_create_user(seed, db):
    r = seed.admin.post("/api/users", json={
        "username": "newteacher", "password": PASSWORD, "password_confirm": PASSWORD,
        "display_name": "새선생", "role": "teacher",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "newteacher" and body["role"] == "teacher"
    assert db("SELECT user_id FROM teacher_profiles WHERE user_id=?", (body["id"],))

    r = seed.admin.post("/api/users", json={
        "username": "staff1", "password": PASSWORD, "password_confirm": PASSWORD,
        "display_name": "x", "role": "staff",
    })
    assert r.status_code == 422
    assert r.json()["detail"] == "이미 사용 중인 아이디입니다."


def test_update_user(seed):
    staff_id = seed.user_ids["staff1"]
    r = seed.admin.patch(f"/api/users/{staff_id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    r = seed.admin.patch(f"/api/users/{staff_id}", json={"role": "teacher", "is_active": True})
    assert r.json()["role"] == "teacher" and r.json()["is_active"] is True

    r = seed.admin.patch(f"/api/users/{seed.user_ids['admin']}", json={"is_active": False})
    assert r.status_code == 400
    assert r.json()["detail"] == "현재 로그인한 본인 계정은 비활성화할 수 없습니다."

    r = seed.admin.patch(f"/api/users/{seed.user_ids['admin']}", json={"role": "staff"})
    assert r.status_code == 422

    assert seed.admin.patch("/api/users/9999", json={"role": "staff"}).status_code == 404


def test_reset_password_and_delete(seed, login_as):
    teacher2 = seed.user_ids["teacher2"]
    r = seed.admin.post(f"/api/users/{teacher2}/reset-password",
                        json={"new_password": "abc", "new_password_confirm": "abc"})
    assert r.status_code == 422

    r = seed.admin.post(f"/api/users/{teacher2}/reset-password",
                        json={"new_password": "reset1", "new_password_confirm": "reset1"})
    assert r.status_code == 204
    login_as("teacher2", "reset1")

    assert seed.admin.delete(f"/api/users/{teacher2}").status_code == 204
    assert seed.admin.delete(f"/api/users/{seed.user_ids['admin']}").status_code == 400
    assert seed.admin.delete("/api/users/9999").status_code == 404
