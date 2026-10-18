"""
개발/확인용 목업 데이터를 넣는다. (운영 DB에는 실행하지 않는다)

    backend/.venv/bin/python scripts/seed_sample_data.py

넣는 데이터
- 계정: staff 1명, teacher 3명 (비밀번호는 모두 pass1234). admin(admin/1234)은 앱이 만든다.
- 배우 60명: 프로필 사진(자동 생성 이미지), 일부는 컴카드(PDF/이미지), 활동중/계약만료 섞음
- 선생님별 수업과 배우 배정 (그중 하나는 매일 수업이라 태블릿 출결을 바로 확인할 수 있다)
- 배우 기록 5종, 최근 출결 기록

앱의 service 함수를 그대로 거치므로 정리 규칙(계약 만료일 자동 계산 등)이 실제와 같이 적용된다.
배우가 이미 한 명이라도 있으면 아무것도 하지 않고 멈춘다.
"""
import asyncio
import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi import UploadFile  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.core.config import DB_PATH  # noqa: E402
from app.core.database import open_db  # noqa: E402
from app.core.files import ensure_dirs  # noqa: E402
from app.core.schema import init_db, migrate_legacy_log_tables  # noqa: E402
from app.features.actor_records import service as records_service  # noqa: E402
from app.features.actors import service as actors_service  # noqa: E402
from app.features.actors.service import ActorForm  # noqa: E402
from app.features.attendance import service as attendance_service  # noqa: E402
from app.features.teachers import service as teachers_service  # noqa: E402
from app.features.users import service as users_service  # noqa: E402

rng = random.Random(20261019)  # 매번 같은 데이터가 나오도록 고정
TODAY = date.today()
PASSWORD = "pass1234"

SURNAMES = list("김이박최정강조윤장임한오서신권황안송류홍")
GIVEN_NAMES = [
    "민준", "서준", "도윤", "예준", "시우", "하준", "지호", "주원", "지후", "준우",
    "서연", "서윤", "지우", "하은", "민서", "하윤", "윤서", "지민", "채원", "수아",
    "지안", "은우", "유나", "다은", "현우", "건우", "예린", "소율", "태윤", "가온",
]
MANAGERS = ["곽다윗", "김민지", "이준호", ""]
SCHOOLS = ["한예종 연기과", "동국대 연극학과", "중앙대 연극학과", "서울예대 연기과", "단국대 공연영화학부", "고3 재학", "중학교 2학년", ""]
HOBBIES = ["헬스", "승마", "요가", "필라테스", "러닝", "등산", "캠핑", "독서", "사진", "요리", "베이킹", "피아노", "기타", "드로잉", "수영", "테니스", "골프", "클라이밍", "영화", "여행"]
SPECIALTIES = ["액션", "무술", "태권도", "중국어", "영어", "일본어", "스페인어", "노래", "보컬", "댄스", "안무", "피아노", "바이올린", "승마", "수영", "사투리(경상도)", "사투리(전라도)", "마술", "복싱", "검도"]
BIOS = [
    "카메라 앞에서 자연스러운 표정 연기가 강점.",
    "광고 촬영 경험 다수. 밝은 이미지.",
    "감정선이 깊고 진지한 역할에 어울림.",
    "코믹 연기에 재능이 있음. 순발력 좋음.",
    "아역 경력 있음. 현장 적응이 빠름.",
    "",
]

TEACHERS = [
    ("teacher_kim", "김선생", "카메라연기", [("카메라연기 A반", "월,화,수,목,금,토,일"), ("카메라연기 심화", "화/목")]),
    ("teacher_lee", "이선생", "보컬", [("보컬 기초", "월/수")]),
    ("teacher_park", "박선생", "댄스", [("방송댄스", "금"), ("현대무용", "토")]),
]

CLASS_FEEDBACK = ["발성 연습, 호흡이 좋아짐", "대본 리딩, 감정선 보완 필요", "카메라 시선 처리 연습", "즉흥 연기, 순발력 좋음", "독백 연습, 발음 교정", "오디션 대비 자유연기 점검"]
AUDITIONS = ["광고 오디션 1차", "웹드라마 단역 오디션", "뮤직비디오 주연 오디션", "OTT 시리즈 조연 오디션", "영화 단편 오디션"]
MEETINGS = ["캐스팅 디렉터 미팅, 프로필 전달", "제작사 미팅, 다음 작품 논의", "광고 에이전시 미팅"]
MANAGEMENT = ["프로필 사진 재촬영 필요", "연기 영상 업데이트 요청", "드라마 캐스팅 진행 중", "광고 2건 지원 완료"]
FIRST_MEETINGS = ["첫 미팅. 연기 방향성: 생활 연기 중심으로 시작", "첫 미팅. 특이사항: 주말 촬영 불가", "첫 미팅. 액션 장르 희망, 체력 좋음"]

COLORS = ["#f4a261", "#2a9d8f", "#e76f51", "#264653", "#8ab17d", "#b56576", "#6d597a", "#457b9d", "#e9c46a", "#3d405b"]


def _font(size: int):
    for path in ["/System/Library/Fonts/AppleSDGothicNeo.ttc", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _upload(data: bytes, filename: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename)


def make_photo(name: str, index: int) -> UploadFile:
    """단색 배경 + 실루엣 + 이름이 들어간 프로필 이미지"""
    color = COLORS[index % len(COLORS)]
    img = Image.new("RGB", (600, 800), color)
    d = ImageDraw.Draw(img)
    d.ellipse((200, 170, 400, 370), fill="#f0f0f0")
    d.rounded_rectangle((120, 400, 480, 800), radius=160, fill="#ffffff")
    d.text((300, 90), name, fill="white", font=_font(64), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return _upload(buf.getvalue(), f"photo_{index}.png")


def make_compcard(name: str, index: int, as_pdf: bool) -> UploadFile:
    """가로형 컴카드. PDF 또는 이미지"""
    img = Image.new("RGB", (1200, 800), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 480, 800), fill=COLORS[index % len(COLORS)])
    d.text((540, 120), name, fill="black", font=_font(80))
    d.text((540, 260), "DAMACTORS ENT", fill="#666666", font=_font(40))
    d.text((540, 340), "COMP CARD", fill="#999999", font=_font(36))
    buf = io.BytesIO()
    if as_pdf:
        img.save(buf, format="PDF")
        return _upload(buf.getvalue(), f"compcard_{index}.pdf")
    img.save(buf, format="JPEG", quality=85)
    return _upload(buf.getvalue(), f"compcard_{index}.jpg")


def random_actor(index: int, used_names: set, used_phones: set) -> ActorForm:
    while True:
        name = rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES)
        if name not in used_names:
            used_names.add(name)
            break
    while True:
        phone = f"{rng.randint(0, 9999):04d}"
        if phone not in used_phones:
            used_phones.add(phone)
            break

    gender = rng.choice(["남자", "여자"])
    birth_year = rng.choice(range(1985, 2013))
    height = rng.gauss(176 if gender == "남자" else 163, 6)
    weight = height - (105 if gender == "남자" else 112) + rng.uniform(-6, 6)

    # 계약 시작일: 대부분 최근 1년 이내, 일부는 더 오래전 (→ 계약만료).
    # 30%는 2년 계약, 나머지는 만료일을 비워서 1년으로 자동 계산된다.
    days_ago = rng.randint(10, 330) if rng.random() < 0.75 else rng.randint(400, 365 * 3)
    contract_start = TODAY - timedelta(days=days_ago)
    contract_end = ""
    if rng.random() < 0.3:
        contract_end = (contract_start.replace(year=contract_start.year + 2) - timedelta(days=1)).isoformat()

    return ActorForm(
        name=name,
        manager_name=rng.choice(MANAGERS),
        gender=gender,
        birth_year=str(birth_year),
        height_cm=f"{height:.1f}",
        weight_kg=f"{weight:.1f}",
        school=rng.choice(SCHOOLS),
        hobby=", ".join(rng.sample(HOBBIES, rng.randint(1, 3))),
        specialty=", ".join(rng.sample(SPECIALTIES, rng.randint(1, 3))),
        contract_date=contract_start.isoformat(),
        contract_end_date=contract_end,
        bio=rng.choice(BIOS),
        teacher_user_id="",
        phone_last4=phone,
    )


def past_dates(days_back: int, count: int) -> list[str]:
    return sorted({(TODAY - timedelta(days=rng.randint(1, days_back))).isoformat() for _ in range(count)})


async def seed():
    ensure_dirs()
    await init_db()
    await migrate_legacy_log_tables()

    async with open_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM actors")
        if (await cur.fetchone())[0] > 0:
            print(f"이미 배우 데이터가 있어서 멈춥니다: {DB_PATH}")
            return

        await users_service.ensure_default_admin(db)
        admin = next(u for u in await users_service.list_users(db) if u["role"] == "admin")

        # ---------- 계정 ----------
        print("계정 생성...")
        existing = {u["username"] for u in await users_service.list_users(db)}
        if "staff_choi" not in existing:
            await users_service.create_user(db, "staff_choi", PASSWORD, PASSWORD, "최스태프", "staff")
        teacher_ids = {}
        for username, display, subject, _ in TEACHERS:
            if username not in existing:
                await users_service.create_user(db, username, PASSWORD, PASSWORD, display, "teacher")
        for u in await users_service.list_users(db):
            teacher_ids[u["username"]] = u["id"]
        for username, _, subject, lessons in TEACHERS:
            days = "/".join(dict.fromkeys(d for _, ds in lessons for d in ds.replace("/", ",").split(",")))
            await teachers_service.save_profile(db, teacher_ids[username], subject, days)

        # ---------- 배우 ----------
        print("배우 60명 생성 (사진, 컴카드 이미지 만드는 중)...")
        used_names, used_phones = set(), set()
        actor_ids = []
        for i in range(60):
            form = random_actor(i, used_names, used_phones)
            if rng.random() < 0.4:
                form.teacher_user_id = str(teacher_ids[rng.choice(TEACHERS)[0]])
            photo = make_photo(form.name, i) if rng.random() < 0.85 else None
            compcard = make_compcard(form.name, i, as_pdf=rng.random() < 0.6) if rng.random() < 0.7 else None
            actor_ids.append(await actors_service.create_actor(db, form, photo, compcard, None))

        # ---------- 수업과 배정 ----------
        print("수업과 배우 배정...")
        lesson_ids = []
        for username, _, _, lessons in TEACHERS:
            for lesson_name, lesson_days in lessons:
                lesson_id = await teachers_service.add_lesson(db, teacher_ids[username], lesson_name, lesson_days)
                members = rng.sample(actor_ids, rng.randint(6, 12))
                await teachers_service.replace_lesson_actors(db, lesson_id, members)
                lesson_ids.append((lesson_id, members))

        # ---------- 배우 기록 5종 ----------
        print("배우 기록 생성...")
        record_plan = [
            ("classlogs", CLASS_FEEDBACK, 0, 4),
            ("auditions", AUDITIONS, 0, 3),
            ("casting-meetings", MEETINGS, 0, 2),
            ("casting-management", MANAGEMENT, 0, 2),
            ("first-meetings", FIRST_MEETINGS, 0, 1),
        ]
        for actor_id in actor_ids:
            for path, contents, low, high in record_plan:
                for d in past_dates(180, rng.randint(low, high)):
                    await records_service.create_record(db, admin, path, actor_id, d, rng.choice(contents))

        # ---------- 출결 (최근 2주, 해당 요일 수업만) ----------
        print("최근 출결 기록 생성...")
        teacher_users = {u["id"]: u for u in await users_service.list_users(db)}
        for lesson_id, members in lesson_ids:
            cur = await db.execute("SELECT teacher_user_id, lesson_days FROM teacher_lessons WHERE id = ?", (lesson_id,))
            row = await cur.fetchone()
            teacher = teacher_users[row["teacher_user_id"]]
            for back in range(1, 15):
                day = TODAY - timedelta(days=back)
                weekday = "월화수목금토일"[day.weekday()]
                if weekday not in (row["lesson_days"] or ""):
                    continue
                entries = {}
                for actor_id in members:
                    status = rng.choices(["출석", "지각", "결석", ""], weights=[70, 10, 10, 10])[0]
                    feedback = rng.choice(CLASS_FEEDBACK) if status in ("출석", "지각") and rng.random() < 0.3 else ""
                    entries[actor_id] = {"status": status, "phone_input": "", "feedback": feedback}
                await attendance_service.save_attendance(db, teacher, lesson_id, day.isoformat(), entries)

        cur = await db.execute("""
            SELECT
                (SELECT COUNT(*) FROM actors),
                (SELECT COUNT(*) FROM users),
                (SELECT COUNT(*) FROM teacher_lessons),
                (SELECT COUNT(*) FROM class_logs),
                (SELECT COUNT(*) FROM attendance_logs),
                (SELECT COUNT(*) FROM actors WHERE contract_end_date < date('now','localtime'))
        """)
        actors, users, lessons, logs, attendance, expired = await cur.fetchone()

    print(f"""
완료: {DB_PATH}
  배우 {actors}명 (계약만료 {expired}명), 계정 {users}개, 수업 {lessons}개, 수업일지 {logs}건, 출결 {attendance}건

로그인 계정 (비밀번호)
  admin / 1234          관리자
  staff_choi / {PASSWORD}  스태프
  teacher_kim / {PASSWORD} 선생님 (매일 수업 '카메라연기 A반' → 태블릿 출결 확인용)
  teacher_lee / {PASSWORD}
  teacher_park / {PASSWORD}
""")


if __name__ == "__main__":
    asyncio.run(seed())
