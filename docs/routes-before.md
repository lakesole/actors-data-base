# 리팩터링 전 라우트 목록

> Phase 6 완료로 아래 화면 라우트는 모두 삭제되었다. 대응 API는 `docs/REFACTOR_PROMPT.md` 5장 표와 `/docs`(OpenAPI)에서 확인한다. `/where`는 삭제만 했고 대응 API가 없다.

리팩터링 시작 시점(`main.py`, 커밋 `4ff2c23`) 기준이다. 이후 단계에서 빠진 기능이 없는지 확인할 때 체크리스트로 쓴다.

권한 표기
- **공개**: 로그인 없이 접근 가능
- **로그인**: 로그인한 모든 역할
- **담당**: admin/staff는 항상 가능하고, teacher는 담당 배우(`actors.teacher_user_id` 또는 수업 배정)일 때만 가능

| 메서드 | 경로 | 권한 | 응답 | 기능 |
|---|---|---|---|---|
| GET | `/where` | 공개 | 텍스트 | 디버그용 |
| GET | `/login` | 공개 (로그인 상태면 `/`로 이동) | login.html | auth |
| POST | `/login` | 공개 | 303 `/` 또는 login.html + 에러 | auth |
| GET | `/logout` | 공개 | 303 `/` | auth |
| GET | `/account/password` | 로그인 | account_password.html | auth |
| POST | `/account/password` | 로그인 | 303 `?success=changed` 또는 에러 화면 | auth |
| GET | `/admin/users` | admin | admin_users.html | users |
| POST | `/admin/users/new` | admin | 303 `?success=created` 또는 에러 화면 | users |
| POST | `/admin/users/{user_id}/toggle-active` | admin (본인 불가) | 303 `?success=toggled` | users |
| POST | `/admin/users/{user_id}/change-role` | admin (본인 불가, 마지막 admin 보호) | 303 `?success=role_changed` 또는 에러 화면 | users |
| POST | `/admin/users/{user_id}/reset-password` | admin | 303 `?success=pw_reset_{username}` 또는 에러 화면 | users |
| POST | `/admin/users/{user_id}/delete` | admin (본인 불가, 마지막 admin 보호) | 303 `?success=deleted` | users |
| POST | `/admin/teachers/{teacher_user_id}/save` | admin | 303 `?success=teacher_saved` | teachers |
| POST | `/admin/teachers/{teacher_user_id}/lesson/add` | admin | 303 `?success=teacher_saved` | teachers |
| POST | `/admin/teachers/lesson/{lesson_id}/delete` | admin | 303 `?success=teacher_saved` | teachers |
| POST | `/admin/teachers/lesson/{lesson_id}/actors/save` | admin | 303 `?success=teacher_saved` | teachers |
| GET | `/` | 공개 (teacher는 담당 배우만 표시) | index.html | actors |
| GET | `/actors/new` | admin, staff | actor_new.html | actors |
| POST | `/actors/new` | admin, staff | 303 `/actors/{id}` | actors |
| GET | `/actors/{actor_id}` | 공개 (teacher는 담당 배우만, 탭은 classlog로 고정) | actor_detail.html, 없으면 302 `/` | actors |
| GET | `/actors/{actor_id}/edit` | admin, staff | actor_edit.html | actors |
| POST | `/actors/{actor_id}/edit` | admin, staff | 303 `/actors/{id}?검색조건` | actors |
| POST | `/actors/{actor_id}/delete` | 담당 | 303 `/` | actors |
| POST | `/actors/{actor_id}/videos/{video_id}/delete` | admin, staff | 303 `?tab=video` | actors |
| GET, POST | `/actors/{actor_id}/classlogs/new` | 담당 | classlog_form.html / 303 `?tab=classlog` | actor_records |
| GET, POST | `/actors/{actor_id}/classlogs/{log_id}/edit` | 담당 | classlog_form.html / 303 | actor_records |
| POST | `/actors/{actor_id}/classlogs/{log_id}/delete` | admin, staff | 303 | actor_records |
| GET, POST | `/actors/{actor_id}/auditions/new` | 담당 | audition_form.html / 303 `?tab=auditions` | actor_records |
| GET, POST | `/actors/{actor_id}/auditions/{aud_id}/edit` | 담당 | audition_form.html / 303 | actor_records |
| POST | `/actors/{actor_id}/auditions/{aud_id}/delete` | admin, staff | 303 | actor_records |
| GET, POST | `/actors/{actor_id}/casting-management/new` | 담당 | casting_management_form.html / 303 `?tab=casting_management` | actor_records |
| GET, POST | `/actors/{actor_id}/casting-management/{item_id}/edit` | 담당 | casting_management_form.html / 303 | actor_records |
| POST | `/actors/{actor_id}/casting-management/{item_id}/delete` | admin, staff | 303 | actor_records |
| GET, POST | `/actors/{actor_id}/casting-meetings/new` | 담당 | casting_meeting_form.html / 303 `?tab=casting_meetings` | actor_records |
| GET, POST | `/actors/{actor_id}/casting-meetings/{item_id}/edit` | 담당 | casting_meeting_form.html / 303 | actor_records |
| POST | `/actors/{actor_id}/casting-meetings/{item_id}/delete` | admin, staff | 303 | actor_records |
| GET, POST | `/actors/{actor_id}/first-meetings/new` | 담당 | first_meeting_form.html / 303 `?tab=first_meeting` | actor_records |
| GET, POST | `/actors/{actor_id}/first-meetings/{item_id}/edit` | 담당 | first_meeting_form.html / 303 | actor_records |
| POST | `/actors/{actor_id}/first-meetings/{item_id}/delete` | admin, staff | 303 | actor_records |
| GET | `/attendance` | 로그인 (teacher는 본인 수업만) | attendance.html | attendance |
| POST | `/attendance/save` | 로그인 (teacher는 본인 수업만) | 303 `/attendance?lesson_id=&attendance_date=` | attendance |
| GET | `/attendance/kiosk` | admin (키오스크 모드 켜짐) | attendance_kiosk.html | attendance |
| POST | `/attendance/kiosk/check` | admin | JSON `{ok, message, actor_name?, status?}` | attendance |
| GET | `/attendance/kiosk/exit` | admin (키오스크 모드 꺼짐) | 303 `/attendance` | attendance |
| GET | `/download/merged-compcards/pdf` | 공개 | PDF 또는 404 텍스트 | compcards |
| POST | `/download/selected-compcards/pdf` | 공개 | PDF 또는 404 텍스트 | compcards |
| GET | `/static/...` | 공개 | 정적 파일, 업로드 파일 | - |

## 공통 동작

- **세션**: `damactors_session` 쿠키, 7일, SameSite=Lax. 비활성화된 계정은 다음 요청에서 세션이 지워진다.
- **키오스크 미들웨어**: 세션의 `kiosk_mode`가 켜져 있으면 `/static`, `/login`, `/logout`, `/attendance/kiosk*` 외의 경로는 303 `/attendance/kiosk`로 보낸다. `/`, `/attendance`, `/login`, `/logout`에 들어오면 키오스크 모드가 꺼진다.
- **403 "로그인이 필요합니다."**: Accept 헤더에 `text/html` 또는 `*/*`가 있으면 `alert()` 후 `history.back()` 하는 HTML(200)을 반환한다.
- **그 외 HTTPException**: 예외 핸들러가 다시 raise하기 때문에 **500**이 된다 (`docs/found-issues.md` #1).
- **시작 시 작업**: 테이블 생성, 컬럼 추가, 구버전 `log_date` 컬럼 마이그레이션, 배우 데이터 정리(출생연도, 계약일), 기본 관리자(admin/1234) 생성.
