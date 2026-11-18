# actor_db · 배우 관리 시스템

배우 프로필과 활동 기록, 수업·출결을 한곳에서 관리하는 사내 업무용 웹 애플리케이션입니다.

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)

[주요 기능](#주요-기능) · [빠른 시작](#빠른-시작) · [테스트](#테스트) · [코드 구조](#코드-구조)

## 주요 기능

- **배우 프로필과 컴카드** · 배우 정보를 등록·수정하고 프로필 사진과 컴카드를 관리합니다.
- **활동 기록** · 배우별 오디션, 미팅, 수업 기록과 연기 영상을 관리합니다.
- **수업과 출결** · 선생님별 수업과 수강 배우를 관리하고 태블릿에서 출결을 기록합니다.
- **계정과 권한** · 관리자·스태프·선생님 역할에 따라 기능에 접근합니다.

## 빠른 시작

로컬 개발 환경은 Python 3.11과 Node.js 24 LTS를 기준으로 합니다.

### 백엔드 실행

저장소 루트에서 백엔드를 실행합니다. 처음 실행할 때 `.env.example`을 `.env`로 복사하고, 예시 파일의 생성 명령을 참고해 `SECRET_KEY`를 설정합니다.

```bash
cp .env.example .env
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
```

### 프론트엔드 실행

별도 터미널을 열고 저장소 루트에서 프론트엔드를 실행합니다.

```bash
cd frontend
npm ci
npm run dev
```

> [**앱 열기**](http://localhost:5173) · [**API 문서 열기**](http://localhost:8000/docs)

개발 서버는 `/api`와 `/media` 요청을 백엔드로 전달합니다.

- SQLite DB와 업로드 파일은 기본적으로 `storage/`에 저장됩니다. 저장 위치는 `.env`의 `STORAGE_DIR`에서 바꿀 수 있습니다. PPT 컴카드 미리보기에는 LibreOffice가 필요하며, 실행 파일 위치는 `SOFFICE_PATH`로 지정할 수 있습니다.

### 목업 데이터

빈 로컬 DB에서 화면을 둘러보려면 저장소 루트에서 다음 명령을 실행합니다.

```bash
backend/.venv/bin/python scripts/seed_sample_data.py
```

배우 60명과 사진·컴카드, 선생님 3명, 수업·활동 기록과 최근 2주 출결을 추가합니다. 배우가 이미 있으면 추가 작업을 건너뜁니다.

- 관리자 계정은 `admin`이며 비밀번호는 `1234`입니다.
- 스태프 계정은 `staff_choi`, 선생님 계정은 `teacher_kim`, `teacher_lee`, `teacher_park`입니다. 비밀번호는 모두 `pass1234`입니다.

## 테스트

저장소 루트에서 실행합니다. 백엔드 API 테스트는 임시 DB를 사용합니다.

```bash
(cd backend && .venv/bin/pytest)
(cd frontend && npm run build)
```

브라우저 스모크 테스트는 Chromium과 별도의 빈 임시 DB를 사용합니다. 서버 실행과 테스트 절차는 [e2e/smoke.mjs](frontend/e2e/smoke.mjs) 상단을 참고하세요.

## 코드 구조

- `backend/app/core/`에 설정, DB, 인증과 파일 처리 코드가 있습니다. 기능별 코드는 `backend/app/features/`에서 API, 서비스, 저장소로 나뉩니다.
- `frontend/src/app/`에 라우팅과 레이아웃, `frontend/src/features/`에 기능별 화면, `frontend/src/shared/`에 API 클라이언트와 공용 UI가 있습니다.

[리팩터링 기록](docs/REFACTOR_PROMPT.md) · [디자인 시스템 문서](docs/DESIGN_PLAN.md) · [기존 업로드 경로 이전 스크립트](scripts/migrate_uploads_to_media.py)
