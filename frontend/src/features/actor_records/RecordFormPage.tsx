import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Loading, Message } from "../../shared/components/Message";
import { recordsApi } from "./api";
import { recordTypeByPath } from "./recordTypes";

/** 기록 추가/수정. /actors/:actorId/records/:path/new, /actors/:actorId/records/:path/:itemId/edit */
export function RecordFormPage() {
  const params = useParams();
  const navigate = useNavigate();
  const actorId = Number(params.actorId);
  const itemId = params.itemId ? Number(params.itemId) : null;
  const type = recordTypeByPath(params.path ?? "");

  const [date, setDate] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(itemId !== null);

  useEffect(() => {
    if (!type || itemId === null) return;
    recordsApi
      .get(actorId, type.path, itemId)
      .then((item) => {
        setDate(item.date);
        setContent(item.content);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "기록을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [actorId, itemId, type]);

  if (!type) return <p className="muted">알 수 없는 기록 종류입니다.</p>;

  const backUrl = `/actors/${actorId}?tab=${type.tab}`;
  const isNew = itemId === null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!type) return;
    setError("");
    try {
      if (isNew) await recordsApi.create(actorId, type.path, { date, content });
      else await recordsApi.update(actorId, type.path, itemId, { date, content });
      navigate(backUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장하지 못했습니다.");
    }
  }

  return (
    <>
      <div className="detail-top">
        <Link className="back" to={backUrl}>← 뒤로</Link>
        <div></div>
      </div>

      <div className="panel-card" style={{ maxWidth: 720 }}>
        <div className="panel-title" style={{ marginBottom: 12 }}>
          {type.formTitle} {isNew ? "추가" : "수정"}
        </div>

        <Message error={error} />
        {loading ? (
          <Loading />
        ) : (
          <form className="edit-form" onSubmit={onSubmit}>
            <div className="form-grid" style={{ display: "grid", gap: 12 }}>
              <div className="field">
                <label>날짜</label>
                <input type="date" required min="1900-01-01" max="2099-12-31" value={date} onChange={(e) => setDate(e.target.value)} />
              </div>

              <div className="field">
                <label>내용</label>
                {type.multiline ? (
                  <textarea className="input" rows={6} required style={{ width: "100%" }} value={content} onChange={(e) => setContent(e.target.value)} />
                ) : (
                  <input type="text" required placeholder={type.placeholder} value={content} onChange={(e) => setContent(e.target.value)} />
                )}
              </div>
            </div>

            <div className="form-actions">
              <button className="btn primary" type="submit">{isNew ? "추가" : "저장"}</button>
              <Link className="btn" to={backUrl}>취소</Link>
            </div>
          </form>
        )}
      </div>
    </>
  );
}
