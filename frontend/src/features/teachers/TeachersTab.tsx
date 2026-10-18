import { useState, type FormEvent } from "react";
import { Loading, Message } from "../../shared/components/Message";
import { useAsync } from "../../shared/hooks/useAsync";
import { actorsApi } from "../actors/api";
import { teachersApi } from "./api";
import type { ActorBrief, Lesson, Teacher } from "./types";

type Run = (action: () => Promise<unknown>) => Promise<boolean>;

export function TeachersTab() {
  const teachers = useAsync(() => teachersApi.list(), []);
  const allActors = useAsync(() => actorsApi.simple(), []);
  const [openId, setOpenId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ error?: string; success?: string }>({});

  const run: Run = async (action) => {
    setMessage({});
    try {
      await action();
      setMessage({ success: "저장되었습니다." });
      teachers.reload();
      return true;
    } catch (e) {
      setMessage({ error: e instanceof Error ? e.message : "처리하지 못했습니다." });
      return false;
    }
  };

  return (
    <>
      <Message error={message.error || teachers.error || allActors.error} success={message.success} />

      <div className="panel-card" style={{ padding: 20 }}>
        <div className="panel-title" style={{ marginBottom: 16 }}>선생님 관리</div>

        {teachers.loading && !teachers.data && <Loading />}
        {teachers.data && teachers.data.length === 0 && <div className="muted">등록된 teacher 계정이 없습니다.</div>}

        <div style={{ display: "grid", gap: 18 }}>
          {(teachers.data ?? []).map((t) => (
            <TeacherCard
              key={t.id}
              teacher={t}
              open={openId === t.id}
              onToggle={() => setOpenId(openId === t.id ? null : t.id)}
              allActors={allActors.data ?? []}
              run={run}
            />
          ))}
        </div>
      </div>
    </>
  );
}

type CardProps = {
  teacher: Teacher;
  open: boolean;
  onToggle: () => void;
  allActors: ActorBrief[];
  run: Run;
};

function TeacherCard({ teacher, open, onToggle, allActors, run }: CardProps) {
  const [lesson, setLesson] = useState({ lesson_name: "", lesson_days: "" });

  async function onAddLesson(e: FormEvent) {
    e.preventDefault();
    if (await run(() => teachersApi.addLesson(teacher.id, lesson))) setLesson({ lesson_name: "", lesson_days: "" });
  }

  return (
    <div style={{ border: "1px solid #ececec", borderRadius: 16, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{teacher.display_name}</div>
          <div style={{ color: "#666", fontSize: 14, marginTop: 4 }}>
            {teacher.username} · {teacher.is_active ? "활성" : "비활성"}
          </div>
          <div className="teacher-summary-line">
            <span className="chip">teacher</span>
            <span className="chip">수업 {teacher.lessons.length}개</span>
            <span className="chip">전체 배정 배우 {teacher.assigned_actors.length}명</span>
          </div>
          <div style={{ marginTop: 10, color: "#666", fontSize: 14 }}>
            현재 전체 배정 배우: <ActorChips actors={teacher.assigned_actors} />
          </div>
        </div>

        <button type="button" className={`admin-summary-btn ${open ? "active" : ""}`} onClick={onToggle}>
          {open ? "수업 관리 닫기" : "수업 관리 열기"}
        </button>
      </div>

      {open && (
        <div style={{ marginTop: 18, marginBottom: 20 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>수업 관리</div>

          {teacher.lessons.length > 0 ? (
            <div style={{ display: "grid", gap: 12, marginBottom: 12 }}>
              {teacher.lessons.map((l) => <LessonEditor key={l.id} lesson={l} allActors={allActors} run={run} />)}
            </div>
          ) : (
            <div className="muted" style={{ marginBottom: 12 }}>등록된 수업이 없습니다.</div>
          )}

          <form onSubmit={onAddLesson}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 10 }}>
              <input type="text" placeholder="예: 카메라연기" required value={lesson.lesson_name} onChange={(e) => setLesson({ ...lesson, lesson_name: e.target.value })} />
              <input type="text" placeholder="예: 화/목" value={lesson.lesson_days} onChange={(e) => setLesson({ ...lesson, lesson_days: e.target.value })} />
              <button className="btn sm primary" type="submit">수업 추가</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

/** 수업 하나: 삭제, 배우 검색 후 체크해서 배정 저장 */
function LessonEditor({ lesson, allActors, run }: { lesson: Lesson; allActors: ActorBrief[]; run: Run }) {
  const [checked, setChecked] = useState<Set<number>>(() => new Set(lesson.actors.map((a) => a.id)));
  const [keyword, setKeyword] = useState("");

  const k = keyword.trim().toLowerCase();
  const matches = k ? allActors.filter((a) => a.name.toLowerCase().includes(k)) : [];

  function toggle(id: number) {
    const next = new Set(checked);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChecked(next);
  }

  async function onDelete() {
    if (!window.confirm("이 수업을 삭제할까요?")) return;
    await run(() => teachersApi.deleteLesson(lesson.id));
  }

  return (
    <div style={{ border: "1px solid #ececec", borderRadius: 14, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <div>
          <strong>{lesson.lesson_name}</strong>
          {lesson.lesson_days && <span style={{ color: "#666" }}> · {lesson.lesson_days}</span>}
          <span className="chip" style={{ marginLeft: 8 }}>배우 {lesson.actor_count}명</span>
        </div>
        <button className="btn sm danger" type="button" onClick={onDelete}>수업 삭제</button>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); run(() => teachersApi.setLessonActors(lesson.id, [...checked])); }}>
        <input
          type="text"
          placeholder="이 수업 배우 검색..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ marginBottom: 10, width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
        />

        <div style={{ maxHeight: 280, overflow: "auto", border: "1px solid #ececec", borderRadius: 12, padding: 12, marginBottom: 12 }}>
          {matches.length === 0 ? (
            <div style={{ padding: "18px 10px", textAlign: "center", color: "#888", fontSize: 14 }}>
              {k ? "검색 결과가 없습니다." : "배우 이름을 검색하면 결과가 표시됩니다."}
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 10 }}>
              {matches.map((a) => (
                <label key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid #eee", borderRadius: 10, padding: "10px 12px", cursor: "pointer" }}>
                  <input type="checkbox" checked={checked.has(a.id)} onChange={() => toggle(a.id)} />
                  <span>{a.name}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginBottom: 10, color: "#666", fontSize: 14 }}>
          현재 수업 배우: <ActorChips actors={lesson.actors} />
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button className="btn sm primary" type="submit">이 수업 배우 저장</button>
        </div>
      </form>
    </div>
  );
}

function ActorChips({ actors }: { actors: ActorBrief[] }) {
  if (actors.length === 0) return <>없음</>;
  return (
    <>
      {actors.map((a) => (
        <span key={a.id} className="chip" style={{ marginRight: 6, marginBottom: 6 }}>{a.name}</span>
      ))}
    </>
  );
}
