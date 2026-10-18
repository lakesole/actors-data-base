from conftest import PASSWORD, assert_login_alert


def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200


def test_login_with_wrong_password_shows_error(client):
    r = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 200
    assert "아이디 또는 비밀번호가 올바르지 않습니다." in r.text


def test_login_with_unknown_user_shows_error(client):
    r = client.post("/login", data={"username": "nobody", "password": "1234"})
    assert r.status_code == 200
    assert "아이디 또는 비밀번호가 올바르지 않습니다." in r.text


def test_login_success_redirects_home(client):
    r = client.post("/login", data={"username": "  admin ", "password": "1234"})
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert client.get("/account/password").status_code == 200


def test_logged_in_user_visiting_login_is_redirected(login_as):
    admin = login_as("admin", "1234")
    r = admin.get("/login")
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_inactive_user_cannot_login(seed, client):
    seed.admin.post(f"/admin/users/{seed.user_ids['staff1']}/toggle-active")
    r = client.post("/login", data={"username": "staff1", "password": PASSWORD})
    assert r.status_code == 200
    assert "비활성화된 계정입니다." in r.text


def test_deactivated_user_session_is_dropped(seed):
    seed.admin.post(f"/admin/users/{seed.user_ids['staff1']}/toggle-active")
    assert_login_alert(seed.staff.get("/account/password"))


def test_logout_clears_session(seed):
    r = seed.staff.get("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert_login_alert(seed.staff.get("/account/password"))


def test_login_required_shows_alert_for_browser(client):
    r = client.get("/account/password", headers={"accept": "text/html"})
    assert_login_alert(r)


def test_password_change_validation(seed):
    def change(current, new, confirm):
        return seed.staff.post("/account/password", data={
            "current_password": current,
            "new_password": new,
            "new_password_confirm": confirm,
        })

    r = change("wrong", "newpass", "newpass")
    assert "현재 비밀번호가 올바르지 않습니다." in r.text

    r = change(PASSWORD, "abc", "abc")
    assert "새 비밀번호는 4자 이상이어야 합니다." in r.text

    r = change(PASSWORD, "newpass", "other")
    assert "새 비밀번호 확인이 일치하지 않습니다." in r.text


def test_password_change_success(seed, login_as):
    r = seed.staff.post("/account/password", data={
        "current_password": PASSWORD,
        "new_password": "newpass",
        "new_password_confirm": "newpass",
    })
    assert r.status_code == 303
    assert r.headers["location"] == "/account/password?success=changed"
    login_as("staff1", "newpass")
