import type { RecordType } from "./types";

/** 기록 5종. 배우 상세 화면의 탭 순서와 같다. */
export const RECORD_TYPES: RecordType[] = [
  {
    path: "class-logs", tab: "classlog", tabLabel: "트레이닝 피드백", panelTitle: "트레이닝 피드백",
    formTitle: "수업일지", emptyText: "아직 수업일지 항목이 없습니다.", placeholder: "예: 발성 트레이닝", multiline: false,
  },
  {
    path: "auditions", tab: "auditions", tabLabel: "오디션", panelTitle: "오디션 영상",
    formTitle: "오디션", emptyText: "아직 오디션 항목이 없습니다.", placeholder: "예: 광고 오디션 1차", multiline: false,
  },
  {
    path: "first-meetings", tab: "first_meeting", tabLabel: "방향성 및 특이사항", panelTitle: "방향성 및 특이사항",
    formTitle: "첫 미팅 기록", emptyText: "아직 기록이 없습니다.", multiline: true,
  },
  {
    path: "casting-management", tab: "casting_management", tabLabel: "캐스팅관리", panelTitle: "캐스팅관리 기록",
    formTitle: "캐스팅관리 기록", emptyText: "아직 캐스팅관리 기록이 없습니다.", multiline: true,
  },
  {
    path: "casting-meetings", tab: "casting_meetings", tabLabel: "캐스팅 미팅", panelTitle: "캐스팅 미팅 기록",
    formTitle: "캐스팅 미팅 기록", emptyText: "아직 캐스팅 미팅 기록이 없습니다.", multiline: true,
  },
];

export const recordTypeByPath = (path: string) => RECORD_TYPES.find((t) => t.path === path);
export const recordTypeByTab = (tab: string) => RECORD_TYPES.find((t) => t.tab === tab);
