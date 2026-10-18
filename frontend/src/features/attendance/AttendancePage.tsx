import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Loading, Message } from "../../shared/components/Message";
import { digitsOnly } from "../../shared/format";
import { useAsync } from "../../shared/hooks/useAsync";
import { attendanceApi } from "./api";
import { STATUS_OPTIONS, type AttendanceEntry } from "./types";

export function AttendancePage() {
  const [search, setSearch] = useSearchParams();
  const lessonId = search.get("lesson_id") ?? "";
  const date = search.get("attendance_date") ?? "";

  const { data, error, loading, reload } = useAsync(() => attendanceApi.get(lessonId, date), [lessonId, date]);
  const [entries, setEntries] = useState<Record<number, AttendanceEntry>>({});
  const [message, setMessage] = useState<{ error?: string; success?: string }>({});

  // 불러온 출결 값으로 입력칸을 채운다
  useEffect(() => {
    if (!data) return;
    const next: Record<number, AttendanceEntry> = {};
    for (const a of data.actors) {
      next[a.id] = {
        actor_id: a.id,
        phone_input: a.phone_input ?? "",
        status: !a.status || a.status === "미체크" ? "" : a.status,
        feedback: a.feedback ?? "",
      };
    }
    setEntries(next);
  }, [data]);

  function select(changes: { lesson_id?: string; attendance_date?: string }) {
    setMessage({});
    const next = new URLSearchParams(search);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setSearch(next);
  }

  const update = (actorId: number, changes: Partial<AttendanceEntry>) =>
    setEntries((prev) => ({ ...prev, [actorId]: { ...prev[actorId], ...changes } }));

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!data?.selected_lesson) return;
    setMessage({});
    try {
      await attendanceApi.save({
        lesson_id: data.selected_lesson.id,
        attendance_date: data.attendance_date,
        entries: Object.values(entries),
      });
      setMessage({ success: "출결이 저장되었습니다." });
      reload();
    } catch (err) {
      setMessage({ error: err instanceof Error ? err.message : "저장하지 못했습니다." });
    }
  }

  return (
    <>
      <div className="page-top" style={{ marginBottom: 18 }}>
        <div>
          <h1 className="page-title">출결 관리</h1>
          <div className="page-sub">수업별 출결 체크 + 피드백 저장</div>
        </div>
      </div>

      <Message error={message.error || error} success={message.success} />

      <div className="panel-card" style={{ padding: 20, marginBottom: 18 }}>
        <div className="form">
          <div className="grid-form" style={{ gridTemplateColumns: "1.2fr 220px auto", alignItems: "end" }}>
            <div className="field">
              <label>수업 선택</label>
              <select value={data?.lesson_id ?? lessonId} onChange={(e) => select({ lesson_id: e.target.value })}>
                <option value="">수업 선택</option>
                {(data?.lessons ?? []).map((l) => (
                  <option key={l.id} value={String(l.id)}>
                    {l.lesson_name || "이름 없는 수업"}
                    {l.lesson_days ? ` · ${l.lesson_days}` : ""}
                    {l.teacher_name ? ` · ${l.teacher_name}` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>날짜</label>
              <input type="date" min="1900-01-01" max="2099-12-31" value={data?.attendance_date ?? date} onChange={(e) => select({ attendance_date: e.target.value })} />
            </div>
            <div className="field">
              <button className="btn primary" type="button" onClick={() => reload()}>조회</button>
            </div>
          </div>
        </div>
      </div>

      {loading && !data && <Loading />}

      {data && !data.selected_lesson && (
        <div className="panel-card" style={{ padding: 20 }}>
          <p className="muted" style={{ margin: 0 }}>수업을 선택하면 배우 출결 목록이 표시됩니다.</p>
        </div>
      )}

      {data?.selected_lesson && (
        <div className="panel-card" style={{ padding: 20 }}>
          <div style={{ marginBottom: 16 }}>
            <div className="panel-title" style={{ marginBottom: 6 }}>{data.selected_lesson.lesson_name || "이름 없는 수업"}</div>
            <div className="muted">
              날짜: {data.attendance_date}
              {data.selected_lesson.lesson_days ? ` · ${data.selected_lesson.lesson_days}` : ""}
            </div>
          </div>

          {data.actors.length === 0 ? (
            <p className="muted">이 수업에 배정된 배우가 없습니다.</p>
          ) : (
            <form onSubmit={onSave}>
              <div style={{ overflowX: "auto" }}>
                <table className="actor-list-table" style={{ minWidth: 1100 }}>
                  <thead>
                    <tr>
                      <th style={{ width: 70 }}>번호</th>
                      <th style={{ width: 180 }}>이름</th>
                      <th style={{ width: 120 }}>등록 뒷번호</th>
                      <th style={{ width: 140 }}>입력</th>
                      <th style={{ width: 160 }}>출결 상태</th>
                      <th>피드백</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.actors.map((a, i) => {
                      const entry = entries[a.id];
                      if (!entry) return null;
                      return (
                        <tr key={a.id}>
                          <td>{i + 1}</td>
                          <td>
                            <strong>{a.name}</strong>
                            {a.birth_year && <div className="muted" style={{ marginTop: 4 }}>{a.birth_year}년생</div>}
                          </td>
                          <td>{a.phone_last4 ? <span className="chip">{a.phone_last4}</span> : <span className="muted">미등록</span>}</td>
                          <td>
                            <input type="text" inputMode="numeric" maxLength={4} placeholder="1234" value={entry.phone_input}
                              onChange={(e) => update(a.id, { phone_input: digitsOnly(e.target.value, 4) })} />
                          </td>
                          <td>
                            <select value={entry.status} onChange={(e) => update(a.id, { status: e.target.value })}>
                              {STATUS_OPTIONS.map(([value, label]) => <option key={label} value={value}>{label}</option>)}
                            </select>
                          </td>
                          <td>
                            <input type="text" placeholder="예: 발성 좋음 / 집중도 보통 / 감정선 좋음" value={entry.feedback}
                              onChange={(e) => update(a.id, { feedback: e.target.value })} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="form-actions" style={{ marginTop: 18 }}>
                <button className="btn primary" type="submit">출결 저장</button>
                <button className="btn" type="button" onClick={() => reload()}>새로고침</button>
              </div>
            </form>
          )}
        </div>
      )}
    </>
  );
}
