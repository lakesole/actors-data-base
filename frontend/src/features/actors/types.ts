export type ContractStatus = "active" | "expired";

export type Actor = {
  id: number;
  name: string;
  gender: string | null;
  birth_year: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  school: string | null;
  hobby: string | null;
  specialty: string | null;
  bio: string | null;
  manager_name: string | null;
  teacher_user_id: number | null;
  phone_last4: string | null;
  contract_date: string | null;
  contract_end_date: string | null;
  photo_path: string | null;
  photo_thumb_path: string | null;
  compcard_path: string | null;
  compcard_preview_path: string | null;
  contract_status: ContractStatus | null;
  contract_status_label: string | null;
  teacher_user_name: string | null;
  ai_score: number | null;
  ai_matched: string[];
};

export type AiParsed = {
  gender: string;
  birth_group: string;
  height_group: string;
  keywords: string[];
  raw: string;
};

export type LessonBrief = {
  id: number;
  lesson_name: string | null;
  lesson_days: string | null;
};

export type ActorList = {
  items: Actor[];
  total_count: number;
  total_pages: number;
  page: number;
  per_page: number;
  ai_parsed: AiParsed | null;
  teacher_lessons: LessonBrief[];
};

export type ActorBrief = { id: number; name: string };

export type Video = {
  id: number;
  actor_id: number;
  video_path: string;
  original_name: string | null;
  created_at: string;
};

/** 배우 등록/수정 폼의 텍스트 필드 */
export type ActorFields = {
  name: string;
  manager_name: string;
  teacher_user_id: string;
  phone_last4: string;
  gender: string;
  birth_year: string;
  height_cm: string;
  weight_kg: string;
  school: string;
  hobby: string;
  specialty: string;
  contract_date: string;
  contract_end_date: string;
  bio: string;
};

export type ActorFiles = {
  photo?: File | null;
  compcard?: File | null;
  acting_videos?: File[];
};
