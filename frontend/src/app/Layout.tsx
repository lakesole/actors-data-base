import { useEffect, useState, type FormEvent } from "react";
import { Link, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "./AuthContext";

/** 상단바(검색, 사용자 메뉴)와 본문. 기존 base.html에 해당한다. */
export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();

  // 목록 화면의 검색어를 상단 입력칸에 보여준다
  const onList = location.pathname === "/";
  const [q, setQ] = useState("");
  const [m, setM] = useState("");
  const [aiQuery, setAiQuery] = useState("");

  useEffect(() => {
    if (!onList) return;
    setQ(params.get("q") ?? "");
    setM(params.get("m") ?? "");
    setAiQuery(params.get("ai_query") ?? "");
  }, [onList, params]);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams();
    const values: Record<string, string> = { q, m, ai_query: aiQuery };
    // 필터와 정렬은 유지하고 페이지는 처음으로
    for (const key of ["gender", "height_group", "birth_group", "sort", "per_page", "view", "status_filter"]) {
      if (onList && params.get(key)) values[key] = params.get(key)!;
    }
    for (const [key, value] of Object.entries(values)) if (value.trim()) next.set(key, value.trim());
    navigate(`/?${next.toString()}`);
  }

  async function onLogout() {
    await logout();
    navigate("/");
  }

  return (
    <>
      <header className="topbar">
        <div className="wrap topbar-inner">
          <Link className="brand-link" to="/">
            <span className="brand">Damactors 배우 DB</span>
          </Link>

          <form className="top-search" onSubmit={onSearch}>
            <input className="inp" type="text" placeholder="배우 이름 검색" value={q} onChange={(e) => setQ(e.target.value)} />
            <input className="inp" type="text" placeholder="담당 매니저 검색" value={m} onChange={(e) => setM(e.target.value)} />
            <input
              className="inp ai-inp"
              type="text"
              placeholder="AI 검색 예: 헬스하는 남자 리스트"
              value={aiQuery}
              onChange={(e) => setAiQuery(e.target.value)}
            />
            <button className="btn primary" type="submit">검색</button>
          </form>

          <div className="hint" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {user ? (
              <>
                <span>{user.display_name} ({user.role})</span>
                {user.role === "admin" && <Link className="btn" to="/admin/users">계정관리</Link>}
                <Link className="btn" to="/attendance">출결</Link>
                {user.role === "admin" && <Link className="btn" to="/attendance/kiosk">태블릿출결</Link>}
                <Link className="btn" to="/account/password">비밀번호 변경</Link>
                <button className="btn" type="button" onClick={onLogout}>로그아웃</button>
              </>
            ) : user === null ? (
              <>
                <span>보기 전용</span>
                <Link className="btn" to="/login">로그인</Link>
              </>
            ) : null}
          </div>
        </div>
      </header>

      <main className="wrap">
        <Outlet />
      </main>
    </>
  );
}
