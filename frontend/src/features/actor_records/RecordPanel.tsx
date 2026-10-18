import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { Loading, Message } from "../../shared/components/Message";
import { useAsync } from "../../shared/hooks/useAsync";
import { recordsApi } from "./api";
import type { RecordType } from "./types";

/** 배우 상세 화면의 기록 탭 내용 (목록 + 추가/수정/삭제) */
export function RecordPanel({ actorId, type }: { actorId: number; type: RecordType }) {
  const { user, hasRole } = useAuth();
  const { data, error, loading, reload } = useAsync(() => recordsApi.list(actorId, type.path), [actorId, type.path]);
  const [actionError, setActionError] = useState("");

  async function onDelete(id: number) {
    if (!window.confirm("이 항목을 삭제할까요?")) return;
    setActionError("");
    try {
      await recordsApi.remove(actorId, type.path, id);
      reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "삭제하지 못했습니다.");
    }
  }

  const base = `/actors/${actorId}/records/${type.path}`;

  return (
    <div className="panel-card">
      <div className="tab-top">
        <div className="panel-title">{type.panelTitle}</div>
        {user && <Link className="btn primary" to={`${base}/new`}>+ 추가</Link>}
      </div>

      <Message error={error || actionError} />
      {loading && !data && <Loading />}

      {data && data.length > 0 && (
        <div className="items">
          {data.map((it) => (
            <div className="item" key={it.id}>
              <div className="item-main">
                <div className="item-date">{it.date}</div>
                <div className="item-text">{it.content}</div>
              </div>
              <div className="item-actions">
                {user && <Link className="btn sm" to={`${base}/${it.id}/edit`}>수정</Link>}
                {hasRole("admin", "staff") && (
                  <button className="btn sm danger" type="button" onClick={() => onDelete(it.id)}>삭제</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {data && data.length === 0 && <p className="muted">{type.emptyText}</p>}
    </div>
  );
}
