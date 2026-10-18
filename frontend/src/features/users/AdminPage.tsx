import { useState } from "react";
import { TeachersTab } from "../teachers/TeachersTab";
import { AccountsTab } from "./AccountsTab";
import "./admin.css";

/** 계정 / 선생님 관리 (관리자 전용) */
export function AdminPage() {
  const [tab, setTab] = useState<"accounts" | "teachers">("accounts");

  return (
    <>
      <div className="page-top" style={{ marginBottom: 20 }}>
        <div>
          <h1 className="page-title">계정 / 선생님 관리</h1>
          <div className="page-sub">관리자 전용</div>
        </div>
      </div>

      <div className="admin-tabs">
        <button type="button" className={`admin-tab-btn ${tab === "accounts" ? "active" : ""}`} onClick={() => setTab("accounts")}>계정 관리</button>
        <button type="button" className={`admin-tab-btn ${tab === "teachers" ? "active" : ""}`} onClick={() => setTab("teachers")}>선생님 관리</button>
      </div>

      {tab === "accounts" ? <AccountsTab /> : <TeachersTab />}
    </>
  );
}
