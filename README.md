# actor_db

배우 관리 시스템 (FastAPI + SQLite + Jinja2).
구조 정리 계획과 진행 상황은 [docs/REFACTOR_PROMPT.md](docs/REFACTOR_PROMPT.md)에 있다.

## 폴더 구조

```
backend/
  app/
    main.py          앱 생성, 라우터 등록
    core/            기능 공통 (설정, DB, 인증, 파일, 예외)
    features/<기능>/  router.py → service.py → repository.py
    templates/       Jinja2 화면 (Phase 6에서 프론트엔드로 대체 예정)
    static/          CSS, 이미지, 업로드 파일
  tests/             특성 테스트
scripts/             일회성 스크립트
storage/             DB 파일 (git 제외)
docs/                구조 정리 문서
```

## 개발 실행

```bash
cp .env.example .env          # SECRET_KEY 채우기
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
```

DB는 기본으로 `storage/actors.db`를 쓴다. 다른 파일을 쓰려면 `.env`의 `DB_PATH`를 바꾼다.

## 테스트

```bash
cd backend
.venv/bin/pytest
```

임시 DB와 임시 업로드 폴더를 쓰므로 실제 데이터는 건드리지 않는다.

## Docker

```bash
cp .env.example .env          # SECRET_KEY 필수
docker compose up -d --build
```

- DB: `./storage/actors.db` (컨테이너의 `/storage`)
- 업로드 파일: `./backend/app/static/uploads`
