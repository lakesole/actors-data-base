export const NO_PROFILE_IMAGE = "/images/no_profile.png";

/** 값이 비어 있으면 "-" */
export function dash(value: string | number | null | undefined): string | number {
  return value === null || value === undefined || value === "" ? "-" : value;
}

/** 소수점 없이 표시 (키, 몸무게). 비어 있으면 "-" */
export function round0(value: number | null | undefined): string {
  return value ? value.toFixed(0) : "-";
}

/** 숫자만 남기고 최대 maxLength 글자 */
export function digitsOnly(value: string, maxLength: number): string {
  return value.replace(/[^0-9]/g, "").slice(0, maxLength);
}

/** 입력 중인 날짜를 YYYY-MM-DD 모양으로 맞춘다 */
export function formatDateTyping(value: string): string {
  let v = value.replace(/[^0-9]/g, "").slice(0, 8);
  if (v.length >= 5) v = `${v.slice(0, 4)}-${v.slice(4)}`;
  if (v.length >= 8) v = `${v.slice(0, 7)}-${v.slice(7)}`;
  return v;
}

/** 계약 시작일 기준 1년 뒤 전날. 형식이 맞지 않으면 빈 문자열 */
export function defaultContractEndDate(start: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start)) return "";
  const date = new Date(start);
  if (Number.isNaN(date.getTime())) return "";
  date.setFullYear(date.getFullYear() + 1);
  date.setDate(date.getDate() - 1);
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

export function todayString(): string {
  const now = new Date();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${m}-${d}`;
}
