import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await login(username, password);
      const next = params.get("next");
      navigate(next && next.startsWith("/") && !next.startsWith("/login") ? next : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    }
  }

  return (
    <div className="form-wrap" style={{ maxWidth: 460, margin: "40px auto" }}>
      <h1 className="form-title">로그인</h1>

      <form className="form" onSubmit={onSubmit}>
        <div className="grid-form" style={{ gridTemplateColumns: "1fr" }}>
          <div className="field">
            <label>아이디</label>
            <input type="text" required placeholder="아이디 입력" value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label>비밀번호</label>
            <input type="password" required placeholder="비밀번호 입력" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        </div>

        {error && <div style={{ marginTop: 12, color: "#d33", fontSize: 14 }}>{error}</div>}

        <div className="form-actions" style={{ marginTop: 20 }}>
          <button className="btn primary" type="submit">로그인</button>
          <Link className="btn" to="/">취소</Link>
        </div>
      </form>
    </div>
  );
}
