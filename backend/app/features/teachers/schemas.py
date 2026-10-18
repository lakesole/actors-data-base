from typing import Annotated

from pydantic import BaseModel, StringConstraints

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ActorBrief(BaseModel):
    id: int
    name: str


class LessonOut(BaseModel):
    id: int
    lesson_name: str | None
    lesson_days: str | None
    actors: list[ActorBrief]
    actor_count: int


class TeacherOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool
    lesson_subject: str | None
    lesson_days: str | None
    lessons: list[LessonOut]
    assigned_actors: list[ActorBrief]


class TeacherChoiceOut(BaseModel):
    id: int
    username: str
    display_name: str
    lesson_subject: str
    lesson_days: str


class ProfileIn(BaseModel):
    lesson_subject: str = ""
    lesson_days: str = ""


class LessonIn(BaseModel):
    lesson_name: NonBlank
    lesson_days: str = ""


class LessonActorsIn(BaseModel):
    actor_ids: list[int]


class CreatedOut(BaseModel):
    id: int
