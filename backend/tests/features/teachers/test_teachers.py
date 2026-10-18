from conftest import assert_denied


def test_save_teacher_profile(seed, db):
    teacher_id = seed.user_ids["teacher1"]
    r = seed.admin.post(f"/admin/teachers/{teacher_id}/save",
                        data={"lesson_subject": " 연기 ", "lesson_days": " 월,수 "})
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/users?success=teacher_saved"
    row = db("SELECT lesson_subject, lesson_days FROM teacher_profiles WHERE user_id=?", (teacher_id,))[0]
    assert row == {"lesson_subject": "연기", "lesson_days": "월,수"}


def test_save_profile_rejects_non_teacher_and_missing(seed):
    assert_denied(seed.admin.post(f"/admin/teachers/{seed.user_ids['staff1']}/save", data={}))
    assert_denied(seed.admin.post("/admin/teachers/9999/save", data={}))


def test_teacher_routes_require_admin(seed):
    teacher_id = seed.user_ids["teacher1"]
    assert_denied(seed.staff.post(f"/admin/teachers/{teacher_id}/save", data={}))
    assert_denied(seed.staff.post(f"/admin/teachers/{teacher_id}/lesson/add",
                                  data={"lesson_name": "x", "lesson_days": "월"}))
    assert_denied(seed.staff.post(f"/admin/teachers/lesson/{seed.lesson_id}/delete"))
    assert_denied(seed.staff.post(f"/admin/teachers/lesson/{seed.lesson_id}/actors/save", data={}))


def test_add_lesson_with_blank_name_is_ignored(seed, db):
    r = seed.admin.post(f"/admin/teachers/{seed.user_ids['teacher1']}/lesson/add",
                        data={"lesson_name": "  ", "lesson_days": "월"})
    assert r.status_code == 303
    assert len(db("SELECT id FROM teacher_lessons")) == 1


def test_assign_actors_replaces_previous(seed, db):
    r = seed.admin.post(f"/admin/teachers/lesson/{seed.lesson_id}/actors/save",
                        data={"actor_ids": [str(seed.other), "not-a-number"]})
    assert r.status_code == 303
    rows = db("SELECT actor_id FROM lesson_actor_assignments WHERE lesson_id=?", (seed.lesson_id,))
    assert [r["actor_id"] for r in rows] == [seed.other]


def test_assign_actors_to_missing_lesson(seed):
    assert_denied(seed.admin.post("/admin/teachers/lesson/9999/actors/save", data={}))


def test_delete_lesson_removes_assignments(seed, db):
    r = seed.admin.post(f"/admin/teachers/lesson/{seed.lesson_id}/delete")
    assert r.status_code == 303
    assert not db("SELECT id FROM teacher_lessons")
    assert not db("SELECT id FROM lesson_actor_assignments")


def test_admin_page_shows_lessons_and_assigned_actors(seed):
    r = seed.admin.get("/admin/users")
    assert "연기반" in r.text
    assert "배정배우" in r.text
