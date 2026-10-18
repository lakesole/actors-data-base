/**
 * 배우 목록의 검색 조건은 URL 쿼리에 둔다. (새로고침/뒤로가기/상세→목록 복귀에도 유지)
 */
export const LIST_KEYS = [
  "q", "m", "ai_query", "gender", "height_group", "birth_group",
  "sort", "status_filter", "lesson_id", "page", "per_page", "view",
] as const;

export type ListKey = (typeof LIST_KEYS)[number];
export type ListParams = Record<ListKey, string>;

/** 검색 조건만 (페이지, 보기 방식 제외) — PDF 통합 다운로드에 쓴다 */
export const FILTER_KEYS: ListKey[] = ["q", "m", "ai_query", "gender", "height_group", "birth_group", "sort", "status_filter"];

export const SORT_LABELS: Record<string, string> = {
  "": "기본순",
  youngest: "어린순",
  oldest: "많은순",
  new_contract: "최근계약순",
  old_contract: "예전계약순",
};

export const STATUS_LABELS: Record<string, string> = {
  active: "활동중",
  expired: "계약만료",
};

export function readListParams(search: URLSearchParams): ListParams {
  const p = {} as ListParams;
  for (const key of LIST_KEYS) p[key] = search.get(key) ?? "";
  if (!p.view) p.view = "card";
  if (!p.page) p.page = "1";
  if (!p.per_page) p.per_page = "24";
  return p;
}

/** 빈 값과 기본값을 뺀 쿼리 문자열 ("?..." 또는 "") */
export function toSearch(p: Partial<ListParams>): string {
  const out = new URLSearchParams();
  for (const key of LIST_KEYS) {
    const value = p[key];
    if (!value) continue;
    if ((key === "page" && value === "1") || (key === "view" && value === "card") || (key === "per_page" && value === "24")) continue;
    out.set(key, value);
  }
  const s = out.toString();
  return s ? `?${s}` : "";
}

export function pick(p: ListParams, keys: ListKey[]): Record<string, string> {
  return Object.fromEntries(keys.map((k) => [k, p[k]]));
}
