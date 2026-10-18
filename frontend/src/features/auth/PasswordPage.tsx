import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { authApi } from "./api";

export function PasswordPage() {
  const [form, setForm] = useState({ current_password: "", new_password: "", new_password_confirm: "" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);
    try {
      await authApi.changePassword(form);
      setSuccess(true);
      setForm({ current_password: "", new_password: "", new_password_confirm: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "비밀번호를 바꾸지 못했습니다.");
    }
  }

  return (
    <>
      <div className="detail-top">
        <Link className="back" to="/">← 목록으로</Link>
      </div>

      <div className="form-wrap" style={{ maxWidth: 640, margin: "0 auto" }}>
        <h1 className="form-title">비밀번호 변경</h1>

        {error && <div className="alert error" style={{ marginBottom: 16 }}>{error}</div>}
        {success && <div className="alert success" style={{ marginBottom: 16 }}>비밀번호가 변경되었습니다.</div>}

        <form className="form" onSubmit={onSubmit}>
          <div className="grid-form" style={{ gridTemplateColumns: "1fr" }}>
            <div className="field">
              <label>현재 비밀번호</label>
              <input type="password" required value={form.current_password} onChange={set("current_password")} />
            </div>
            <div className="field">
              <label>새 비밀번호</label>
              <input type="password" required value={form.new_password} onChange={set("new_password")} />
            </div>
            <div className="field">
              <label>새 비밀번호 확인</label>
              <input type="password" required value={form.new_password_confirm} onChange={set("new_password_confirm")} />
            </div>
          </div>

          <div className="form-actions" style={{ marginTop: 20 }}>
            <button className="btn primary" type="submit">비밀번호 저장</button>
            <Link className="btn" to="/">취소</Link>
          </div>
        </form>
      </div>
    </>
  );
}
