# actor_db

배우 관리 시스템. 백엔드는 FastAPI + SQLite, 프론트엔드는 React + Vite + TypeScript.
구조 정리 계획과 진행 상황은 [docs/REFACTOR_PROMPT.md](docs/REFACTOR_PROMPT.md)에 있다.

## 폴더 구조

```
backend/
  app/
    main.py          앱 생성, 라우터 등록
    core/            기능 공통 (설정, DB, 인증, 파일, 예외)
    features/<기능>/  api.py(JSON) / router.py(Jinja 화면) → service.py → repository.py
    templates/       Jinja2 화면 (Phase 6에서 제거 예정)
    static/          Jinja 화면용 CSS, 이미지
  tests/             특성 테스트 (화면 + API)
frontend/
  src/app/           라우팅, 레이아웃, 로그인 상태
  src/shared/        API 호출, 공용 컴포넌트, 스타일
  src/features/<기능>/  백엔드 features와 같은 이름
  e2e/               브라우저 스모크 테스트
scripts/             일회성 스크립트
storage/             DB, 업로드 파일 (git 제외)
docs/                구조 정리 문서
```

## 개발 실행

백엔드 (http://localhost:8000, API 문서는 /docs)

```bash
cp .env.example .env          # SECRET_KEY 채우기
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
```

프론트엔드 (http://localhost:5173, `/api`와 `/media`는 백엔드로 프록시)

```bash
cd frontend
npm install
npm run dev
```

DB와 업로드 파일은 기본으로 `storage/`에 저장된다. 위치를 바꾸려면 `.env`의 `STORAGE_DIR`을 바꾼다.

### 목업 데이터 (로컬 확인용)

```bash
backend/.venv/bin/python scripts/seed_sample_data.py
```

배우 60명(사진, 컴카드 포함), 선생님 3명과 수업, 기록, 최근 2주 출결을 만든다. 배우가 이미 있으면 아무것도 하지 않는다.
계정: `admin / 1234`, `staff_choi`, `teacher_kim`, `teacher_lee`, `teacher_park` (비밀번호 `pass1234`)

### 업로드 파일 이전 (기존 운영 데이터, 한 번만)

Phase 4부터 업로드 파일은 `storage/uploads`에 저장되고 `/media/uploads/...`로 서빙된다.
기존 파일(`backend/app/static/uploads`)과 DB의 URL은 아래 스크립트로 옮긴다.

```bash
backend/.venv/bin/python scripts/migrate_uploads_to_media.py           # 미리보기
backend/.venv/bin/python scripts/migrate_uploads_to_media.py --apply   # 실행 (DB 자동 백업)
```

## 테스트

```bash
cd backend && .venv/bin/pytest          # 특성 테스트 (임시 DB 사용)
cd frontend && npm run build            # 타입 검사 + 빌드
cd frontend && npm run e2e              # 브라우저 스모크 테스트 (e2e/smoke.mjs 상단의 준비 방법 참고)
```

## Docker

```bash
cp .env.example .env          # SECRET_KEY 필수
docker compose up -d --build
```

- DB와 업로드 파일: `./storage` (컨테이너의 `/storage`)
- 프론트엔드 컨테이너(nginx)는 Phase 6에서 추가한다. 그 전까지 프론트엔드는 `npm run dev`로 띄운다.
