import { useState, type ChangeEvent, type FormEvent } from "react";
import { useAuth } from "../../app/AuthContext";
import { Loading, Message } from "../../shared/components/Message";
import { useAsync } from "../../shared/hooks/useAsync";
import type { Role } from "../auth/types";
import { usersApi } from "./api";
import { ROLES, type User } from "./types";

const EMPTY_FORM = { display_name: "", username: "", password: "", password_confirm: "", role: "teacher" as Role };

export function AccountsTab() {
  const { user: me } = useAuth();
  const { data: users, error, loading, reload } = useAsync(() => usersApi.list(), []);
  const [form, setForm] = useState(EMPTY_FORM);
  const [openId, setOpenId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ error?: string; success?: string }>({});

  /** 요청을 실행하고 성공/실패 메시지를 보여준 뒤 목록을 다시 불러온다 */
  async function run(action: () => Promise<unknown>, success: string) {
    setMessage({});
    try {
      await action();
      setMessage({ success });
      reload();
      return true;
    } catch (e) {
      setMessage({ error: e instanceof Error ? e.message : "처리하지 못했습니다." });
      return false;
    }
  }

  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [key]: e.target.value });

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (await run(() => usersApi.create(form), "계정이 생성되었습니다.")) setForm(EMPTY_FORM);
  }

  async function onToggleActive(u: User) {
    if (u.is_active && !window.confirm("이 계정을 비활성화할까요?")) return;
    await run(() => usersApi.update(u.id, { is_active: !u.is_active }), "계정 상태가 변경되었습니다.");
  }

  return (
    <>
      <Message error={message.error || error} success={message.success} />

      <div className="admin-two-col">
        <div className="panel-card" style={{ padding: 20 }}>
          <div className="panel-title" style={{ marginBottom: 14 }}>새 계정 만들기</div>
          <form className="form" onSubmit={onCreate}>
            <div className="grid-form" style={{ gridTemplateColumns: "1fr" }}>
              <div className="field"><label>이름</label><input type="text" required placeholder="예: 김선생" value={form.display_name} onChange={set("display_name")} /></div>
              <div className="field"><label>아이디</label><input type="text" required placeholder="예: teacher_kim" value={form.username} onChange={set("username")} /></div>
              <div className="field"><label>비밀번호</label><input type="password" required placeholder="4자 이상" value={form.password} onChange={set("password")} /></div>
              <div className="field"><label>비밀번호 확인</label><input type="password" required placeholder="비밀번호 다시 입력" value={form.password_confirm} onChange={set("password_confirm")} /></div>
              <div className="field">
                <label>권한</label>
                <select required value={form.role} onChange={set("role")}>
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <div className="form-actions" style={{ marginTop: 16 }}>
              <button className="btn primary" type="submit">계정 생성</button>
            </div>
          </form>
        </div>

        <div className="panel-card" style={{ padding: 20 }}>
          <div className="panel-title" style={{ marginBottom: 14 }}>전체 계정 목록</div>
          {loading && !users && <Loading />}
          <div style={{ overflowX: "auto" }}>
            <table className="actor-list-table" style={{ minWidth: 860 }}>
              <thead>
                <tr><th>ID</th><th>이름</th><th>아이디</th><th>권한</th><th>상태</th><th>생성일</th><th>관리</th></tr>
              </thead>
              <tbody>
                {(users ?? []).map((u) => {
                  const isMe = me?.id === u.id;
                  return [
                    <tr key={u.id}>
                      <td>{u.id}</td>
                      <td>{u.display_name}</td>
                      <td>{u.username}</td>
                      <td><span className="chip">{u.role}</span></td>
                      <td>
                        {u.is_active
                          ? <span className="chip" style={{ background: "#eef8ee", color: "#1d6b2f" }}>활성</span>
                          : <span className="chip" style={{ background: "#f3f3f3", color: "#666" }}>비활성</span>}
                      </td>
                      <td>{u.created_at}</td>
                      <td>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {isMe ? (
                            <button className="btn sm" type="button" disabled>본인 계정</button>
                          ) : (
                            <>
                              <button className={`btn sm ${u.is_active ? "danger" : "primary"}`} type="button" onClick={() => onToggleActive(u)}>
                                {u.is_active ? "비활성화" : "활성화"}
                              </button>
                              <button type="button" className={`admin-summary-btn ${openId === u.id ? "active" : ""}`} onClick={() => setOpenId(openId === u.id ? null : u.id)}>
                                관리
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>,
                    openId === u.id && !isMe && (
                      <tr key={`${u.id}-actions`}>
                        <td colSpan={7} style={{ padding: "0 0 16px 0" }}>
                          <AccountActions user={u} run={run} onDeleted={() => setOpenId(null)} />
                        </td>
                      </tr>
                    ),
                  ];
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

type ActionsProps = {
  user: User;
  run: (action: () => Promise<unknown>, success: string) => Promise<boolean>;
  onDeleted: () => void;
};

/** 계정별 관리 패널: 권한 변경, 비밀번호 재설정, 삭제 */
function AccountActions({ user, run, onDeleted }: ActionsProps) {
  const [role, setRole] = useState<Role>(user.role);
  const [pw, setPw] = useState({ new_password: "", new_password_confirm: "" });

  async function onResetPassword(e: FormEvent) {
    e.preventDefault();
    if (await run(() => usersApi.resetPassword(user.id, pw), "비밀번호가 재설정되었습니다.")) {
      setPw({ new_password: "", new_password_confirm: "" });
    }
  }

  async function onDelete() {
    if (!window.confirm("정말 이 계정을 삭제할까요?")) return;
    if (await run(() => usersApi.remove(user.id), "계정이 삭제되었습니다.")) onDeleted();
  }

  return (
    <div className="account-action-panel">
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 180px", gap: 16, alignItems: "start" }}>
        <form style={{ margin: 0 }} onSubmit={(e) => { e.preventDefault(); run(() => usersApi.update(user.id, { role }), "권한이 변경되었습니다."); }}>
          <div style={{ fontWeight: 700, marginBottom: 10 }}>권한 변경</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
            <select required value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button className="btn sm" type="submit">권한 저장</button>
          </div>
        </form>

        <form style={{ margin: 0 }} onSubmit={onResetPassword}>
          <div style={{ fontWeight: 700, marginBottom: 10 }}>비밀번호 재설정</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 8 }}>
            <input type="password" placeholder="새 비밀번호" required value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
            <input type="password" placeholder="새 비밀번호 확인" required value={pw.new_password_confirm} onChange={(e) => setPw({ ...pw, new_password_confirm: e.target.value })} />
            <button className="btn sm primary" type="submit">재설정</button>
          </div>
        </form>

        <div>
          <div style={{ fontWeight: 700, marginBottom: 10 }}>계정 삭제</div>
          <button className="btn sm danger" type="button" style={{ width: "100%" }} onClick={onDelete}>계정 삭제</button>
        </div>
      </div>
    </div>
  );
}
