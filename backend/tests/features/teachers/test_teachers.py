def test_list_teachers(seed):
    teachers = seed.admin.get("/api/teachers").json()
    t1 = next(t for t in teachers if t["username"] == "teacher1")
    assert t1["lessons"][0]["lesson_name"] == "연기반"
    assert t1["lessons"][0]["actors"] == [{"id": seed.assigned, "name": "배정배우"}]
    assert t1["assigned_actors"] == [{"id": seed.assigned, "name": "배정배우"}]
    assert seed.staff.get("/api/teachers").status_code == 403


def test_teacher_choices_for_staff(seed):
    choices = seed.staff.get("/api/teachers/choices").json()
    assert {c["username"] for c in choices} == {"teacher1", "teacher2"}
    assert seed.teacher.get("/api/teachers/choices").status_code == 403


def test_profile_and_lessons(seed, db):
    t2 = seed.user_ids["teacher2"]
    assert seed.admin.put(f"/api/teachers/{t2}/profile", json={"lesson_subject": "보컬", "lesson_days": "화"}).status_code == 204
    assert seed.admin.put(f"/api/teachers/{seed.user_ids['staff1']}/profile", json={}).status_code == 400

    r = seed.admin.post(f"/api/teachers/{t2}/lessons", json={"lesson_name": "  ", "lesson_days": "화"})
    assert r.status_code == 422

    r = seed.admin.post(f"/api/teachers/{t2}/lessons", json={"lesson_name": "보컬반", "lesson_days": "화"})
    assert r.status_code == 201
    lesson_id = r.json()["id"]

    r = seed.admin.put(f"/api/teachers/lessons/{lesson_id}/actors", json={"actor_ids": [seed.assigned, seed.other]})
    assert r.status_code == 204
    assert len(db("SELECT id FROM lesson_actor_assignments WHERE lesson_id=?", (lesson_id,))) == 2
    assert seed.admin.put("/api/teachers/lessons/9999/actors", json={"actor_ids": []}).status_code == 404

    assert seed.admin.delete(f"/api/teachers/lessons/{lesson_id}").status_code == 204
    assert not db("SELECT id FROM lesson_actor_assignments WHERE lesson_id=?", (lesson_id,))


def test_profile_is_trimmed(seed, db):
    teacher_id = seed.user_ids["teacher1"]
    r = seed.admin.put(f"/api/teachers/{teacher_id}/profile", json={"lesson_subject": " 연기 ", "lesson_days": " 월,수 "})
    assert r.status_code == 204
    row = db("SELECT lesson_subject, lesson_days FROM teacher_profiles WHERE user_id=?", (teacher_id,))[0]
    assert row == {"lesson_subject": "연기", "lesson_days": "월,수"}
    assert seed.admin.put("/api/teachers/9999/profile", json={}).status_code in (400, 404)


def test_teacher_routes_require_admin(seed):
    teacher_id = seed.user_ids["teacher1"]
    assert seed.staff.put(f"/api/teachers/{teacher_id}/profile", json={}).status_code == 403
    assert seed.staff.post(f"/api/teachers/{teacher_id}/lessons", json={"lesson_name": "x"}).status_code == 403
    assert seed.staff.delete(f"/api/teachers/lessons/{seed.lesson_id}").status_code == 403
    assert seed.staff.put(f"/api/teachers/lessons/{seed.lesson_id}/actors", json={"actor_ids": []}).status_code == 403


def test_assign_actors_replaces_previous(seed, db):
    r = seed.admin.put(f"/api/teachers/lessons/{seed.lesson_id}/actors", json={"actor_ids": [seed.other]})
    assert r.status_code == 204
    rows = db("SELECT actor_id FROM lesson_actor_assignments WHERE lesson_id=?", (seed.lesson_id,))
    assert [r["actor_id"] for r in rows] == [seed.other]
