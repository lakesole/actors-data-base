# 리팩터링 중 발견한 문제

리팩터링 원칙(동작 보존)에 따라 **고치지 않고 기록만** 한다. 각 항목은 별도 작업으로 수정 여부를 결정한다.
특성 테스트(`backend/tests`)는 현재 동작을 기준으로 작성되어 있어서, 수정하면 관련 테스트도 함께 바꿔야 한다.

| # | 심각도 | 위치 (리팩터링 후) | 내용 |
|---|---|---|---|
| 1 | 높음 | `core/errors.py` | **로그인 필요 외의 모든 HTTPException이 500으로 바뀐다.** 예외 핸들러가 처리하지 않는 경우 `raise exc`로 다시 던져서, 권한 없음(403), 잘못된 날짜(400), 없음(404)이 전부 "Internal Server Error"로 보인다. 브라우저가 아닌 요청(Accept에 html이 없는 경우)은 로그인 필요도 500이 된다. 수정: `raise exc` 대신 `return await fastapi.exception_handlers.http_exception_handler(request, exc)`. |
| 2 | 높음 | `features/compcards/router.py` | **컴카드 PDF 다운로드 2개에 권한 검사가 없다.** 로그인하지 않아도 검색 조건으로 전체 배우의 컴카드를 받을 수 있다. |
| 3 | 높음 | `features/actors/router.py` 삭제 | **담당 teacher가 배우를 삭제할 수 있다.** 삭제가 `require_actor_edit_permission`으로 검사된다. 화면에는 삭제 버튼이 admin에게만 보이지만 요청을 직접 보내면 삭제된다. 사용되지 않는 `can_delete_actor`/`require_actor_delete_permission`(admin만)이 원래 의도로 보인다. |
| 4 | 중간 | `features/actors/router.py` 목록, 상세 | **로그인하지 않아도 배우 목록과 상세(개인정보 포함)를 볼 수 있다.** |
| 5 | 중간 | `features/users/service.py` | 기본 관리자 계정이 `admin / 1234`로 만들어진다. 운영 DB에서 비밀번호를 바꿨는지 확인이 필요하다. |
| 6 | 중간 | `features/actors/service.py` 목록 | teacher가 **AI 검색**을 쓰면 `actors.teacher_user_id`로 직접 배정된 배우만 나오고, 수업 배정으로 연결된 배우는 빠진다. 일반 검색은 둘 다 나온다. |
| 7 | 낮음 | `features/attendance/router.py` 저장 | `lesson_id`가 숫자가 아니면 `int()` 변환 오류로 500이 난다. |
| 8 | 낮음 | `features/teachers/router.py` 수업 추가 | 수업 추가 시 대상이 teacher 계정인지, 존재하는 계정인지 확인하지 않는다. |
| 9 | 낮음 | `features/actors/service.py` 생성 | `phone_last4`가 숫자의 **앞 4자리**를 저장한다. 전화번호 전체(010-1234-5678)를 입력하면 `0101`이 저장된다. |
| 10 | 낮음 | 앱 시작 | `normalize_actor_data()`가 시작할 때마다 모든 배우 행을 UPDATE 한다. 데이터가 많아지면 시작이 느려진다. |
| 11 | 낮음 | `features/users` 권한 변경/삭제 | "마지막 관리자 보호" 분기는 실제로 도달할 수 없다. 요청자가 admin이고 본인은 대상에서 제외되므로 대상 admin이 마지막일 수 없다. 기능상 문제는 없다. |
| 12 | 정보 | `main.py` | `/where` 디버그 라우트가 운영에 노출되어 있다. |
| 13 | 중간 | `features/actors/router.py` 생성/수정 | **연기영상을 여러 개 올려도 마지막 1개만 저장된다.** `acting_videos: list[UploadFile] \| UploadFile \| None` 유니온 타입을 FastAPI가 단일 파일로 해석한다. 수정: `acting_videos: list[UploadFile] = File([])`. |
| 14 | 낮음 | 폼 전체 | 필수 폼 필드(`Form(...)`)를 빈 값으로 보내면 FastAPI가 422 JSON을 반환해서, "아이디, 비밀번호, 이름은 필수입니다." 같은 화면 메시지는 공백만 입력했을 때만 나온다. |
