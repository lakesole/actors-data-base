import io

from pypdf import PdfWriter


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_merged_and_selected(seed, client):
    r = client.get("/api/compcards/merged.pdf")
    assert r.status_code == 404
    assert r.json()["detail"] == "통합 가능한 PDF 파일이 없습니다."

    r = seed.staff.post("/api/actors", data={"name": "컴카드배우"},
                        files=[("compcard", ("c.pdf", _pdf_bytes(), "application/pdf"))])
    actor_id = r.json()["id"]

    r = client.get("/api/compcards/merged.pdf", params={"q": "컴카드"})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")

    r = client.post("/api/compcards/selected.pdf", json={"actor_ids": [actor_id]})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")

    r = client.post("/api/compcards/selected.pdf", json={"actor_ids": [seed.other]})
    assert r.status_code == 404

    assert client.post("/api/compcards/selected.pdf", json={"actor_ids": []}).status_code == 422


def _create_actor_with_compcard(seed, filename, content, content_type="application/octet-stream"):
    r = seed.staff.post("/api/actors", data={"name": "컴카드배우"},
                        files=[("compcard", (filename, content, content_type))])
    assert r.status_code == 201
    return r.json()["id"]


def test_pdf_compcard_is_its_own_preview(seed, db):
    actor_id = _create_actor_with_compcard(seed, "card.pdf", _pdf_bytes(), "application/pdf")
    row = db("SELECT compcard_path, compcard_preview_path FROM actors WHERE id=?", (actor_id,))[0]
    assert row["compcard_path"].endswith(".pdf")
    assert row["compcard_preview_path"] == row["compcard_path"]


def test_ppt_compcard_without_converter_has_no_preview(seed, db):
    actor_id = _create_actor_with_compcard(seed, "card.pptx", b"not-a-real-pptx")
    row = db("SELECT compcard_path, compcard_preview_path FROM actors WHERE id=?", (actor_id,))[0]
    assert row["compcard_path"].endswith(".pptx")
    assert row["compcard_preview_path"] is None


def test_download_headers(seed, client):
    _create_actor_with_compcard(seed, "card.pdf", _pdf_bytes(), "application/pdf")
    # 현재는 로그인 없이도 다운로드된다 (docs/found-issues.md #2)
    r = client.get("/api/compcards/merged.pdf?q=컴카드")
    assert r.headers["content-type"] == "application/pdf"
    assert "merged_compcards_" in r.headers["content-disposition"]
