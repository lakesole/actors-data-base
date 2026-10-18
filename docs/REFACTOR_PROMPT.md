# Actor DB 구조 정리 프롬프트

> 이 문서는 AI 코딩 에이전트(Claude Code 등)에게 그대로 전달하는 작업 지시서다.
> 한 세션에서 **한 단계(Phase)만** 진행하고, 단계가 끝나면 멈춰서 결과를 보고한다.
> 시작할 때: `docs/REFACTOR_PROMPT.md의 Phase N을 진행해줘`

---

## 0. 설정값

작업 전에 아래 값을 확인한다. 바꾸고 싶으면 이 표만 수정한다.

| 항목 | 값 |
|---|---|
| 백엔드 | Python 3.11, FastAPI, aiosqlite (SQLite 유지) |
| 프론트엔드 | React + Vite + TypeScript |
| 인증 방식 | 세션 쿠키 유지 (JWT로 바꾸지 않음) |
| 배포 | docker-compose (NAS) |
| 작업 브랜치 | `refactor/structure` |

---

## 1. 목표

1. **3계층 구조 (Spring 방식)**: Router(Controller) → Service → Repository
2. **백엔드/프론트엔드 완전 분리**: 백엔드는 JSON API만 제공하고, 화면은 전부 프론트엔드가 그린다.
3. **코로케이션 폴더 구조**: 파일 종류가 아니라 **기능(feature)** 단위로 폴더를 나눈다. 한 기능의 router, service, repository, schema는 같은 폴더에 둔다.
4. **동작 보존**: 사용자 입장에서 기능, 권한, 데이터는 바뀌지 않는다. 구조만 바뀐다.

---

## 2. 현재 상태 (출발점)

- `actor_db/main.py` 한 파일(약 4,100줄)에 라우트 약 70개, DB 스키마, 인증, 파일 처리, AI 검색이 모두 들어 있다.
- 화면은 Jinja2 템플릿 15개(`actor_db/templates/`)로 서버에서 렌더링한다.
- DB: SQLite `actors.db`, `aiosqlite`로 SQL을 직접 실행한다.
  - 테이블: `actors`, `acting_videos`, `class_logs`, `auditions`, `casting_management_logs`, `casting_meetings`, `first_meetings`, `users`, `teacher_profiles`, `teacher_lessons`, `lesson_actor_assignments`, `attendance_logs`
  - 스키마 생성과 컬럼 추가 마이그레이션이 `init_db()`와 그 위쪽 함수에 흩어져 있다.
- 인증: Starlette `SessionMiddleware`에 `user_id`를 저장한다. 역할은 `admin`, `staff`, `teacher` 3가지다.
  - `require_*` 함수들(`require_admin`, `require_actor_edit_permission`, `require_record_delete_permission` 등)이 403을 발생시킨다.
  - teacher는 **담당 배우만** 접근할 수 있다(`teacher_can_access_actor`).
- 키오스크 모드: 미들웨어 `kiosk_mode_guard`가 세션의 `kiosk_mode` 값에 따라 경로를 제한한다.
- 403 핸들러가 HTML `alert()` 스크립트를 반환한다. 분리 후에는 프론트엔드에서 처리해야 한다.
- 파일: 업로드는 `static/uploads/`, 병합 결과는 `static/merged/`에 저장한다. DB에는 `/static/uploads/...` 형태의 URL이 저장되어 있다.
- 컴카드: python-pptx로 병합하고, LibreOffice(`soffice`)로 PDF/미리보기를 만들고, pypdf로 PDF를 병합한다.
- 알려진 문제
  - 시크릿 키가 코드에 하드코딩되어 있다 (`SessionMiddleware(secret_key=...)`).
  - `__pycache__`, `actor_db/.DS_Store`가 git에 커밋되어 있다. `.gitignore`가 거의 비어 있다.
  - `services/pdf_convert.py`는 사용되지 않는다 (NAS 경로와 `sudo docker exec`가 하드코딩됨). main.py에 같은 기능을 하는 중복 구현이 있다.
  - import 중복, `@app.on_event("startup")` 사용(deprecated).

---

## 3. 최종 폴더 구조

```
Actor_db2/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docs/
│   └── REFACTOR_PROMPT.md
├── scripts/                         # 일회성 스크립트 (compress_images.py, make_thumbs.py)
├── storage/                         # 런타임 데이터, git 제외, 도커 볼륨
│   ├── actors.db
│   ├── uploads/
│   └── merged/
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── tests/
│   │   ├── conftest.py              # 임시 DB, 로그인된 클라이언트 fixture
│   │   └── features/<기능명>/test_*.py
│   └── app/
│       ├── main.py                  # 앱 생성, 미들웨어, 라우터 등록만
│       ├── core/                    # 기능 공통 (기능 폴더는 core에만 의존)
│       │   ├── config.py            # 환경변수 (SECRET_KEY, STORAGE_DIR, ...)
│       │   ├── database.py          # 연결 의존성, transaction(), init_db 호출
│       │   ├── schema.py            # CREATE TABLE, 컬럼 추가 마이그레이션 (한 곳에 모음)
│       │   ├── security.py          # 비밀번호 해시/검증
│       │   ├── auth.py              # get_current_user, require_role 등 Depends
│       │   ├── errors.py            # 도메인 예외 → JSON 에러 응답 변환
│       │   ├── files.py             # 업로드 저장, 썸네일, 파일 삭제
│       │   └── validators.py        # 날짜, 출생연도 정리 등
│       └── features/
│           ├── auth/                # 로그인, 로그아웃, 내 정보, 비밀번호 변경
│           ├── users/               # 관리자: 계정 생성/권한 변경/비활성화/삭제
│           ├── teachers/            # 강사 프로필, 수업(lesson), 수업-배우 배정
│           ├── actors/              # 배우 목록/상세/생성/수정/삭제, 영상
│           │   ├── router.py
│           │   ├── service.py
│           │   ├── repository.py
│           │   ├── schemas.py
│           │   └── search.py        # AI_KEYWORD_MAP, parse_ai_query, 점수 계산
│           ├── actor_records/       # 수업일지, 오디션, 캐스팅 관리, 캐스팅 미팅, 첫 미팅
│           ├── attendance/          # 출석부, 키오스크
│           └── compcards/           # 컴카드 PPT 병합, PDF 변환/다운로드
│               ├── router.py
│               ├── service.py
│               ├── pptx_merge.py
│               └── pdf_convert.py   # LibreOffice 호출 (중복 구현을 하나로 통합)
│
└── frontend/
    ├── Dockerfile                   # 빌드 후 nginx로 서빙 + /api, /media 프록시
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts               # 개발 시 /api, /media → localhost:8000 프록시
    └── src/
        ├── main.tsx
        ├── app/                     # 라우팅, 레이아웃(base.html 대체), 인증 가드
        ├── shared/
        │   ├── api/http.ts          # fetch 래퍼 (credentials, 에러 처리, 401/403 처리)
        │   ├── components/          # Button, FormField, Modal 등 공용 UI
        │   └── styles/              # 기존 style.css 이전
        └── features/                # 백엔드 features와 이름을 1:1로 맞춘다
            ├── auth/
            │   ├── api.ts
            │   ├── types.ts
            │   ├── LoginPage.tsx
            │   └── PasswordPage.tsx
            ├── users/
            ├── teachers/
            ├── actors/
            ├── actor_records/
            ├── attendance/
            └── compcards/
```

**코로케이션 규칙**
- 한 기능에 필요한 파일은 그 기능 폴더 안에 둔다. 기능 폴더를 지우면 그 기능이 깔끔하게 사라져야 한다.
- 두 개 이상의 기능이 **실제로** 사용하는 코드만 `core/`(백엔드) 또는 `shared/`(프론트)로 올린다. "나중에 쓸 것 같아서"는 이유가 되지 않는다.
- 백엔드 `features/x`와 프론트 `features/x`는 같은 이름을 쓴다.
- 파일이 작으면 굳이 쪼개지 않는다. 기능 폴더 안 파일이 400줄을 넘으면 그때 나눈다.

---

## 4. 3계층 규칙 (Spring 대응)

| 계층 | 파일 | Spring 대응 | 하는 일 | 하면 안 되는 일 |
|---|---|---|---|---|
| Router | `router.py` | `@RestController` | 요청 파싱, `Depends`로 사용자/DB 주입, service 호출, schema로 응답 | SQL 실행, 비즈니스 규칙, 권한 판단 로직 직접 작성 |
| Service | `service.py` | `@Service` + `@Transactional` | 비즈니스 규칙, 권한 판단(담당 배우 여부 등), 트랜잭션 경계, 여러 repository 조합 | `Request`/`Response`/`Form` 등 HTTP 객체 사용, SQL 직접 작성 |
| Repository | `repository.py` | `@Repository` | SQL 실행, 결과를 dict/dataclass로 반환 | `commit()`, 권한 판단, HTTPException 발생 |
| Schema | `schemas.py` | DTO | Pydantic 요청/응답 모델 | 로직 |

**의존 방향**
```
router → service → repository → core.database
          ↓
   (다른 기능의) service     ← 허용
   (다른 기능의) repository  ← 금지. 반드시 그 기능의 service를 거친다
   router → router          ← 금지
```

**트랜잭션**
- `core/database.py`에 `get_db()` 의존성(요청마다 연결 하나)과 `transaction(db)` 컨텍스트 매니저를 둔다.
- `commit`/`rollback`은 service의 `async with transaction(db):` 블록에서만 일어난다.

**예외**
- service는 HTTP를 모른다. `NotFound`, `Forbidden`, `ValidationFailed` 같은 도메인 예외를 `core/errors.py`에 정의해서 발생시킨다.
- `core/errors.py`의 예외 핸들러가 이것을 `{"detail": "...", "code": "..."}` JSON과 404/403/422 상태 코드로 변환한다.
- 기존 한국어 에러 메시지는 그대로 유지한다.

**예시 (수업일지 생성)**
```python
# features/actor_records/router.py
@router.post("/actors/{actor_id}/class-logs", status_code=201, response_model=ClassLogOut)
async def create_class_log(actor_id: int, body: ClassLogIn,
                           user: User = Depends(require_login), db=Depends(get_db)):
    return await service.create_class_log(db, user, actor_id, body)

# features/actor_records/service.py
async def create_class_log(db, user, actor_id, body):
    await actors_service.ensure_can_edit(db, user, actor_id)   # 다른 기능은 service로 접근
    async with transaction(db):
        new_id = await repository.insert_class_log(db, actor_id, body.meet_date, body.content, now_iso())
    return await repository.get_class_log(db, new_id)

# features/actor_records/repository.py
async def insert_class_log(db, actor_id, meet_date, content, created_at) -> int:
    cur = await db.execute(
        "INSERT INTO class_logs (actor_id, meet_date, content, created_at) VALUES (?, ?, ?, ?)",
        (actor_id, meet_date, content, created_at))
    return cur.lastrowid
```

---

## 5. API 설계 규칙

- 모든 API는 `/api` 접두어를 쓴다. 업로드 파일은 `/media/...`로 서빙한다.
- 폼 POST + 303 리다이렉트를 REST로 바꾼다.

| 현재 | 변경 후 |
|---|---|
| `POST /login`, `GET /logout` | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |
| `GET /` (목록, 검색, 정렬) | `GET /api/actors?q=&ai=&sort=` |
| `GET /actors/{id}` | `GET /api/actors/{id}` |
| `POST /actors/new` | `POST /api/actors` (multipart: 사진, 컴카드 포함) |
| `POST /actors/{id}/edit` | `PATCH /api/actors/{id}` |
| `POST /actors/{id}/delete` | `DELETE /api/actors/{id}` |
| `POST /actors/{id}/classlogs/new` | `POST /api/actors/{id}/class-logs` |
| `POST /actors/{id}/classlogs/{log_id}/edit` | `PATCH /api/actors/{id}/class-logs/{log_id}` |
| `POST /actors/{id}/classlogs/{log_id}/delete` | `DELETE /api/actors/{id}/class-logs/{log_id}` |
| 오디션, 캐스팅 관리, 캐스팅 미팅, 첫 미팅 | 위와 같은 패턴 (`auditions`, `casting-management`, `casting-meetings`, `first-meetings`) |
| `POST /admin/users/{id}/toggle-active` 등 | `PATCH /api/users/{id}` (is_active, role), `POST /api/users/{id}/reset-password` |
| `POST /attendance/kiosk/check` | `POST /api/attendance/kiosk/check` (이미 JSON이므로 응답 형식 유지) |
| `GET /download/merged-compcards/pdf` | `GET /api/compcards/merged.pdf` |
| `GET /new`, `/edit` 같은 폼 화면 | 삭제 (프론트엔드 라우트가 담당) |

- 응답 상태 코드: 조회 200, 생성 201, 삭제 204, 권한 없음 403, 로그인 필요 401, 없음 404, 검증 실패 422.
- **"로그인이 필요합니다"는 403이 아니라 401로 바꾼다.** 프론트엔드는 401을 받으면 로그인 화면으로 보낸다. 기존 `alert()` HTML 핸들러는 삭제한다.
- 날짜는 `YYYY-MM-DD` 문자열을 유지한다 (DB 형식과 동일).

**세션과 프록시**
- 세션 쿠키 방식을 유지한다. 프론트와 백엔드를 **같은 origin**으로 묶어서 CORS를 사용하지 않는다.
  - 개발: Vite dev server가 `/api`, `/media`를 `localhost:8000`으로 프록시
  - 운영: nginx가 정적 파일을 서빙하고 `/api`, `/media`를 backend 컨테이너로 프록시
- 키오스크 모드는 세션 값을 그대로 쓴다. 백엔드 미들웨어는 `/api/*` 중 키오스크에서 허용된 API 외에는 403 `{"code": "KIOSK_MODE"}`를 반환한다. 프론트엔드는 이 코드를 받으면 키오스크 화면으로 이동한다.

---

## 6. 단계별 진행

### 진행 현황

- [x] Phase 0. 안전장치
- [x] Phase 1. 저장소 정리
- [x] Phase 2. 백엔드 뼈대와 core 분리
- [ ] Phase 3. 기능별 3계층 분리 (Jinja 화면 유지)
  - [x] auth
  - [x] teachers
  - [x] users
  - [x] actors
  - [x] actor_records
  - [ ] attendance
  - [ ] compcards
- [ ] Phase 4. JSON API 추가
- [ ] Phase 5. 프론트엔드 구축
- [ ] Phase 6. Jinja 제거와 배포

> 단계를 끝내면 해당 단계의 체크박스와 위 진행 현황을 함께 체크한다.

각 단계는 **독립적으로 배포 가능한 상태**로 끝나야 한다. 단계 중간에 앱이 깨진 채로 커밋하지 않는다.

### Phase 0. 안전장치
- [x] `refactor/structure` 브랜치를 만든다.
- [x] `actors.db`를 `actors.db.bak-YYYYMMDD`로 백업한다 (git에는 올리지 않는다).
- [x] 현재 라우트 전체 목록(메서드, 경로, 필요 권한)을 `docs/routes-before.md`로 기록한다. 이후 단계에서 누락 여부를 확인하는 체크리스트로 쓴다.
- [x] `pytest` + `TestClient`(httpx 기반)로 **현재 main.py 기준** 특성 테스트(characterization test)를 작성한다. 임시 DB 복사본을 사용한다.
   - 최소 범위: 로그인 성공/실패, 역할별(admin/staff/teacher) 배우 수정 권한, teacher의 담당 외 배우 접근 거부, 수업일지 생성/수정/삭제, 키오스크 출석 체크.

- [x] **완료 조건**: 테스트가 현재 코드에서 전부 통과한다.

### Phase 1. 저장소 정리
- [x] `.gitignore`에 `__pycache__/`, `*.pyc`, `.venv/`, `.DS_Store`, `*.db`, `*.db.bak-*`, `storage/`, `node_modules/`, `dist/`, `.env`를 추가한다.
- [x] 이미 추적 중인 파일을 `git rm --cached`로 제외한다 (`__pycache__`, `.DS_Store`, `data/test.pptx`). **파일 자체는 삭제하지 않는다.**
- [x] 시크릿 키, DB 경로, 저장소 경로를 환경변수로 옮긴다. `.env.example`을 만든다.
- [x] import 중복을 정리한다.

- [x] **완료 조건**: 앱이 기존과 동일하게 동작하고, Phase 0 테스트가 통과한다.

### Phase 2. 백엔드 뼈대와 core 분리
- [x] `actor_db/`를 `backend/app/`로 옮기는 폴더 구조를 만든다. Dockerfile과 docker-compose 경로를 수정한다.
- [x] `core/`로 옮긴다: config, database(`get_db`, `transaction`), schema(`init_db`와 흩어진 마이그레이션 전체), security, auth(`get_current_user`, `require_*`), files, validators.
- [x] `@app.on_event("startup")`을 `lifespan`으로 바꾼다.
- [x] 이 단계에서는 **라우트 코드는 아직 main.py에 남겨두고**, main.py가 core를 import해서 쓰게만 바꾼다.

- [x] **완료 조건**: main.py에 SQL 스키마와 인증 함수가 남아 있지 않고, 테스트가 통과한다.

### Phase 3. 기능별 3계층 분리 (Jinja 화면 유지)
기능 하나씩, 아래 순서로 옮긴다. **기능 하나가 끝날 때마다 테스트 실행 후 커밋한다.**

순서: `auth` → `teachers` → `users` → `actors` → `actor_records` → `attendance` → `compcards`

각 기능마다:
- [ ] SQL을 `repository.py`로 옮긴다. **SQL 문장은 바꾸지 않는다.**
- [ ] 비즈니스 규칙과 권한 판단을 `service.py`로 옮긴다.
- [ ] 라우트는 `router.py`(`APIRouter`)로 옮긴다. 이 단계의 router는 **아직 Jinja 템플릿을 반환해도 된다.** 화면이 그대로 동작하게 하는 것이 목표다.
- [ ] 템플릿은 일단 그대로 `backend/app/templates/`에 둔다 (Phase 6에서 삭제할 예정이라 코로케이션하지 않는다).

`actor_records` 참고: 5종 기록은 모양이 비슷하다. 필드가 같은 부분만 공통 헬퍼로 묶고, 필드가 다르면 억지로 하나의 제네릭으로 합치지 않는다.

`compcards` 참고: LibreOffice 호출을 `pdf_convert.py` 하나로 통합하고, 기존 `services/pdf_convert.py`(미사용)는 삭제한다. soffice 실행 경로는 환경변수로 받는다.

- [ ] **완료 조건**: main.py가 앱 생성과 라우터 등록만 남아 100줄 이하이고, 테스트가 통과하며, 화면 동작이 기존과 같다.

### Phase 4. JSON API 추가
- [ ] 각 기능에 `schemas.py`(Pydantic)를 만든다.
- [ ] 5장 표에 따라 `/api/...` 라우트를 추가한다. **Phase 3에서 만든 service를 그대로 재사용한다.** service에 화면 전용 로직이 섞여 있으면 이때 분리한다.
- [ ] `core/errors.py`에 도메인 예외 → JSON 핸들러를 추가한다. 401/403을 구분한다.
- [ ] 업로드 파일을 `storage/uploads`로 옮기고 `/media`로 서빙한다. DB에 저장된 `/static/uploads/...` URL을 `/media/uploads/...`로 바꾸는 **일회성 마이그레이션 스크립트**를 `scripts/`에 작성한다. 실행 전에 백업을 확인하고, 실행은 사용자에게 확인받는다.
- [ ] 기존 Jinja 라우트는 아직 지우지 않는다 (두 방식이 공존).
- [ ] 테스트를 API 기준으로 추가한다. Phase 0의 시나리오를 API로 다시 검증한다.

- [ ] **완료 조건**: `docs/routes-before.md`의 모든 기능에 대응하는 API가 있고, `/docs`(OpenAPI)에서 확인할 수 있다.

### Phase 5. 프론트엔드 구축
- [ ] `frontend/`에 Vite + React + TypeScript 프로젝트를 만든다. dev 프록시를 설정한다.
- [ ] `shared/api/http.ts`: `credentials: "include"`, JSON 에러 파싱, 401이면 로그인 화면으로, `KIOSK_MODE`면 키오스크 화면으로 보낸다.
- [ ] `app/`: 라우터, 공통 레이아웃(base.html 대체), 역할 기반 라우트 가드.
- [ ] 기존 `style.css`를 `shared/styles/`로 옮겨서 화면 모양을 최대한 유지한다. 디자인 개편은 이 작업 범위가 아니다.
- [ ] 기능별로 화면을 옮긴다. 순서는 Phase 3과 같다. 각 기능 폴더에 `api.ts`, `types.ts`, `*Page.tsx`, 해당 기능 전용 컴포넌트를 둔다.
- [ ] 템플릿 → 화면 대응

| Jinja 템플릿 | 프론트 기능 폴더 |
|---|---|
| login.html, account_password.html | auth |
| admin_users.html | users, teachers |
| index.html, actor_detail.html, actor_new.html, actor_edit.html | actors |
| classlog_form.html, audition_form.html, casting_management_form.html, casting_meeting_form.html, first_meeting_form.html | actor_records |
| attendance.html, attendance_kiosk.html | attendance |
| base.html | app (레이아웃) |

- [ ] **완료 조건**: 프론트엔드만으로 모든 기능을 사용할 수 있다. 역할별(admin/staff/teacher)과 키오스크 모드를 직접 확인한다.

### Phase 6. Jinja 제거와 배포
- [ ] 백엔드에서 Jinja 라우트, `templates/`, `static/`, `jinja2` 의존성을 삭제한다. 백엔드에는 `/api`와 `/media`만 남는다.
- [ ] `frontend/Dockerfile`(빌드 → nginx)과 `nginx.conf`를 작성한다.
- [ ] docker-compose를 `backend`, `frontend`(nginx) 두 서비스로 구성한다. `storage/`는 backend에 볼륨으로 연결한다. LibreOffice가 backend 이미지에 포함되는지, 별도 컨테이너인지 현재 NAS 구성을 확인하고 맞춘다.
- [ ] README에 개발 실행 방법(backend, frontend 각각)과 배포 방법을 정리한다.

- [ ] **완료 조건**: `docker compose up` 하나로 전체가 뜨고, 백엔드 코드에 HTML을 반환하는 곳이 없다.

---
## 7. 작업 규칙 (에이전트용)

- **한 번에 한 Phase만** 진행한다. 끝나면 변경 요약, 테스트 결과, 다음 Phase에서 주의할 점을 보고하고 멈춘다.
- 기능 단위로 커밋한다. 커밋 메시지 형식: `refactor(actors): repository/service 분리`
- **동작을 바꾸지 않는다.** 리팩터링 중 버그를 발견하면 고치지 말고 `docs/found-issues.md`에 기록한 뒤 보고한다. (예외: 5장에 명시된 401 변경, URL 변경)
- DB 스키마는 바꾸지 않는다. 테이블/컬럼 추가, 이름 변경 금지. 유일한 예외는 Phase 4의 파일 URL 마이그레이션이다.
- `actors.db`, `storage/`의 실제 데이터를 삭제하거나 덮어쓰는 명령은 실행 전에 반드시 사용자에게 확인받는다.
- 테스트가 실패하면 테스트를 고쳐서 통과시키지 않는다. 원인이 리팩터링이면 코드를 고치고, 원래 동작이 테스트와 다르면 보고한다.
- 새 라이브러리 추가는 최소화한다. 추가할 때는 이유를 보고에 적는다.
