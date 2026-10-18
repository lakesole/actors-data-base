import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { attendanceApi } from "./api";
import type { KioskInfo } from "./types";
import "./kiosk.css";

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

/** 태블릿 출결. 상단바 없이 전체 화면으로 띄운다. 이 화면을 열면 세션이 키오스크 모드가 된다. */
export function KioskPage() {
  const navigate = useNavigate();
  const [info, setInfo] = useState<KioskInfo | null>(null);
  const [digits, setDigits] = useState("");
  const [message, setMessage] = useState<{ text: string; type: "" | "success" | "error" }>({ text: "", type: "" });
  const submitting = useRef(false);

  useEffect(() => {
    attendanceApi.kioskInfo().then(setInfo).catch((e) => setMessage({ text: e.message, type: "error" }));
  }, []);

  function reset() {
    setDigits("");
    setMessage({ text: "", type: "" });
    submitting.current = false;
  }

  async function submit(value: string) {
    if (submitting.current) return;
    submitting.current = true;
    try {
      const result = await attendanceApi.kioskCheck(value);
      setMessage({ text: result.message || (result.ok ? "출석 완료" : "처리 실패"), type: result.ok ? "success" : "error" });
    } catch {
      setMessage({ text: "저장 중 오류가 발생했습니다.", type: "error" });
    }
    setTimeout(reset, 1800);
  }

  function press(d: string) {
    if (submitting.current || digits.length >= 4) return;
    const next = digits + d;
    setDigits(next);
    if (next.length === 4) submit(next);
  }

  function backspace() {
    if (!submitting.current) setDigits(digits.slice(0, -1));
  }

  function submitManual() {
    if (digits.length !== 4) {
      setMessage({ text: "4자리를 입력해주세요.", type: "error" });
      return;
    }
    submit(digits);
  }

  async function exitKiosk() {
    if (!window.confirm("태블릿 출결을 종료할까요?")) return;
    await attendanceApi.kioskExit();
    navigate("/attendance");
  }

  return (
    <div className="kiosk-page">
      <div className="kiosk-wrap">
        <div className="kiosk-hero" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <p className="kiosk-sub">전화번호 뒤 4자리를 입력하면 자동으로 출석 처리됩니다.</p>
          <button type="button" onClick={exitKiosk} style={{ border: "none", background: "none", color: "#999", fontSize: 12, cursor: "pointer" }}>
            종료
          </button>
        </div>

        <div className="kiosk-date-card">
          <div className="kiosk-label">오늘 날짜</div>
          <div className="kiosk-value">{info?.today_str ?? ""}</div>
        </div>

        <div className="kiosk-main-card">
          <div className="kiosk-screen">
            <div className="kiosk-guide">출결번호를 입력해주세요.</div>
            <div className="kiosk-digits">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className={`kiosk-digit-box ${digits[i] ? "" : "kiosk-empty"}`}>{digits[i] ?? "—"}</div>
              ))}
            </div>
            <div className={`kiosk-message ${message.type ? `kiosk-${message.type}` : ""}`}>{message.text}</div>
          </div>

          <div className="kiosk-pad-title">전화번호 뒤 4자리 입력</div>

          <div className="kiosk-grid">
            {KEYS.map((k) => <button key={k} type="button" className="kiosk-key" onClick={() => press(k)}>{k}</button>)}
            <button type="button" className="kiosk-key kiosk-sub" onClick={reset}>다시입력</button>
            <button type="button" className="kiosk-key" onClick={() => press("0")}>0</button>
            <button type="button" className="kiosk-key kiosk-sub" onClick={backspace}>지우기</button>
          </div>

          <div className="kiosk-bottom">
            <button type="button" className="kiosk-action" onClick={submitManual}>출석</button>
            <button type="button" className="kiosk-action kiosk-secondary" onClick={reset}>초기화</button>
          </div>
        </div>
      </div>
    </div>
  );
}
