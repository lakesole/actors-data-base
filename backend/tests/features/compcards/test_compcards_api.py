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
