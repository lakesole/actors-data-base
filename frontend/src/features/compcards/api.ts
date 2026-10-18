import { downloadFile, toQueryString } from "../../shared/api/http";

export const compcardsApi = {
  /** 목록 검색 조건에 맞는 배우 전체의 PDF 컴카드 통합본 (링크로 바로 받는다) */
  mergedUrl: (filters: Record<string, string>) => `/api/compcards/merged.pdf${toQueryString(filters)}`,

  downloadSelected: (actorIds: number[]) =>
    downloadFile("/api/compcards/selected.pdf", { method: "POST", body: { actor_ids: actorIds } }, "선택컴카드.pdf"),
};
