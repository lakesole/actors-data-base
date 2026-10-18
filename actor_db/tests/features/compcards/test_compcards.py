import io

from pypdf import PdfWriter


def _pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _create_actor_with_compcard(seed, filename, content, content_type):
    r = seed.staff.post(
        "/actors/new",
        data={"name": "컴카드배우"},
        files=[("compcard", (filename, content, content_type))],
    )
    assert r.status_code == 303
    return int(r.headers["location"].rsplit("/", 1)[1])


def test_merged_pdf_without_pdfs(seed):
    r = seed.admin.get("/download/merged-compcards/pdf")
    assert r.status_code == 404
    assert r.text == "통합 가능한 PDF 파일이 없습니다."


def test_pdf_compcard_is_its_own_preview(seed, db):
    actor_id = _create_actor_with_compcard(seed, "card.pdf", _pdf_bytes(), "application/pdf")
    row = db("SELECT compcard_path, compcard_preview_path FROM actors WHERE id=?", (actor_id,))[0]
    assert row["compcard_path"].endswith(".pdf")
    assert row["compcard_preview_path"] == row["compcard_path"]


def test_ppt_compcard_without_converter_has_no_preview(seed, db):
    actor_id = _create_actor_with_compcard(seed, "card.pptx", b"not-a-real-pptx", "application/octet-stream")
    row = db("SELECT compcard_path, compcard_preview_path FROM actors WHERE id=?", (actor_id,))[0]
    assert row["compcard_path"].endswith(".pptx")
    assert row["compcard_preview_path"] is None


def test_merged_pdf_download(seed, client):
    _create_actor_with_compcard(seed, "card.pdf", _pdf_bytes(), "application/pdf")
    # 현재는 로그인 없이도 다운로드된다 (docs/found-issues.md 참고)
    r = client.get("/download/merged-compcards/pdf?q=컴카드")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert "merged_compcards_" in r.headers["content-disposition"]


def test_selected_pdf_download(seed):
    actor_id = _create_actor_with_compcard(seed, "card.pdf", _pdf_bytes(), "application/pdf")

    r = seed.admin.post("/download/selected-compcards/pdf", data={"actor_ids": [str(actor_id), str(seed.other)]})
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")

    r = seed.admin.post("/download/selected-compcards/pdf", data={"actor_ids": [str(seed.other)]})
    assert r.status_code == 404
    assert r.text == "선택한 배우 중 다운로드 가능한 PDF가 없습니다."
