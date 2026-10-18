export type RecordItem = {
  id: number;
  actor_id: number;
  date: string;
  content: string;
  created_at: string;
};

export type RecordType = {
  /** API 경로 조각: /api/actors/{id}/<path> */
  path: string;
  /** 배우 상세 화면 탭 이름 (?tab=) */
  tab: string;
  tabLabel: string;
  panelTitle: string;
  formTitle: string;
  emptyText: string;
  placeholder?: string;
  /** 내용 입력을 여러 줄로 받을지 */
  multiline: boolean;
};
