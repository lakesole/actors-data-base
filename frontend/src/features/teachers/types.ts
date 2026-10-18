export type ActorBrief = { id: number; name: string };

export type Lesson = {
  id: number;
  lesson_name: string | null;
  lesson_days: string | null;
  actors: ActorBrief[];
  actor_count: number;
};

export type Teacher = {
  id: number;
  username: string;
  display_name: string;
  is_active: boolean;
  lesson_subject: string | null;
  lesson_days: string | null;
  lessons: Lesson[];
  assigned_actors: ActorBrief[];
};

export type TeacherChoice = {
  id: number;
  username: string;
  display_name: string;
  lesson_subject: string;
  lesson_days: string;
};
