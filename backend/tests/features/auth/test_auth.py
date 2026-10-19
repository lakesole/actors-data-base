from conftest import PASSWORD


def test_login_me_logout(client):
    r = client.post("/api/auth/login", json={"username": " admin ", "password": "1234"})
    assert r.status_code == 200
    assert r.json() == {"id": 1, "username": "admin", "display_name": "최고관리자", "role": "admin"}

    assert client.get("/api/auth/me").json()["username"] == "admin"

    assert client.post("/api/auth/logout").status_code == 204
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "로그인이 필요합니다.", "code": "LOGIN_REQUIRED"}


def test_login_failures(seed, client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 422
    assert r.json() == {"detail": "아이디 또는 비밀번호가 올바르지 않습니다.", "code": "VALIDATION_FAILED"}

    seed.admin.patch(f"/api/users/{seed.user_ids['staff1']}", json={"is_active": False})
    r = client.post("/api/auth/login", json={"username": "staff1", "password": PASSWORD})
    assert r.json()["detail"] == "비활성화된 계정입니다."


def test_change_password(seed, login_as):
    r = seed.staff.post("/api/auth/password", json={
        "current_password": "wrong", "new_password": "newpass", "new_password_confirm": "newpass",
    })
    assert r.status_code == 422
    assert r.json()["detail"] == "현재 비밀번호가 올바르지 않습니다."

    r = seed.staff.post("/api/auth/password", json={
        "current_password": PASSWORD, "new_password": "newpass", "new_password_confirm": "newpass",
    })
    assert r.status_code == 204
    login_as("staff1", "newpass")


def test_api_errors_are_json(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/json"

    r = client.post("/api/auth/login", json={})
    assert r.status_code == 422


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "1234"})
    assert r.status_code == 422
    assert r.json()["detail"] == "아이디 또는 비밀번호가 올바르지 않습니다."


def test_deactivated_user_session_is_dropped(seed):
    seed.admin.patch(f"/api/users/{seed.user_ids['staff1']}", json={"is_active": False})
    assert seed.staff.get("/api/auth/me").status_code == 401


def test_password_change_validation(seed):
    def change(current, new, confirm):
        r = seed.staff.post("/api/auth/password", json={
            "current_password": current, "new_password": new, "new_password_confirm": confirm,
        })
        assert r.status_code == 422
        return r.json()["detail"]

    assert change(PASSWORD, "abc", "abc") == "새 비밀번호는 4자 이상이어야 합니다."
    assert change(PASSWORD, "newpass", "other") == "새 비밀번호 확인이 일치하지 않습니다."


def test_login_required_is_401_json(client):
    r = client.get("/api/auth/me", headers={"accept": "text/html"})
    assert r.status_code == 401
    assert r.json()["code"] == "LOGIN_REQUIRED"
