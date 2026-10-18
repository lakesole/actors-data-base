type Props = {
  error?: string;
  success?: string;
};

/** 화면 상단 에러/성공 메시지 (관리자 화면에서 쓰던 스타일과 같다) */
export function Message({ error, success }: Props) {
  if (error) {
    return (
      <div style={{ marginBottom: 16, padding: "12px 14px", borderRadius: 12, background: "#fff1f1", color: "#c62828" }}>
        {error}
      </div>
    );
  }
  if (success) {
    return (
      <div style={{ marginBottom: 16, padding: "12px 14px", borderRadius: 12, background: "#eef8ee", color: "#1d6b2f" }}>
        {success}
      </div>
    );
  }
  return null;
}

export function Loading() {
  return <p className="muted">불러오는 중...</p>;
}
