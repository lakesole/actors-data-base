"""
AI 검색(자연어 키워드 검색).

"여자 승마 90년대생" 같은 문장에서 성별, 출생연대, 키, 키워드를 뽑고
배우마다 점수를 매겨 점수가 높은 순으로 정렬한다. DB를 쓰지 않는 순수 함수들이다.
"""
import re

AI_KEYWORD_MAP = {
    "헬스": ["헬스", "운동", "피트니스", "웨이트", "웨이트트레이닝", "자기관리"],
    "운동": ["운동", "헬스", "피트니스", "러닝", "체력", "자기관리"],
    "요가": ["요가", "필라테스", "스트레칭"],
    "필라테스": ["필라테스", "요가", "스트레칭"],
    "액션": ["액션", "무술", "검도", "태권도", "합기도", "운동"],
    "중국어": ["중국어", "중문", "mandarin", "중국어회화"],
    "영어": ["영어", "english", "영어회화"],
    "일본어": ["일본어", "japanese", "일어"],
    "승마": ["승마", "말타기"],
    "수영": ["수영", "스위밍"],
    "춤": ["춤", "댄스", "무용", "안무"],
    "노래": ["노래", "보컬", "가창"],
    "피아노": ["피아노", "건반"],
    "바이올린": ["바이올린", "현악기"],
    "축구": ["축구", "풋볼"],
    "농구": ["농구", "basketball"],
    "러닝": ["러닝", "달리기", "마라톤"],
    "자전거": ["자전거", "사이클", "라이딩"],
    "테니스": ["테니스", "라켓", "서브", "코트"],
    "골프": ["골프", "라운딩", "필드", "스윙"],
    "클라이밍": ["클라이밍", "볼더링", "암벽등반"],
    "등산": ["등산", "트래킹", "하이킹", "산행"],
    "낚시": ["낚시", "피싱", "강태공", "월척"],
    "캠핑": ["캠핑", "차박", "글램핑", "야영"],
    "서핑": ["서핑", "파도타기", "서프"],
    "스케이트보드": ["스케이트보드", "보드", "롱보드"],
    "스키": ["스키", "스노우보드", "설원"],
    "코딩": ["코딩", "프로그래밍", "개발", "소프트웨어"],
    "데이터분석": ["데이터분석", "데이터사이언스", "빅데이터"],
    "인공지능": ["인공지능", "AI", "머신러닝", "딥러닝"],
    "웹디자인": ["웹디자인", "퍼블리싱", "UIUX"],
    "영상편집": ["영상편집", "유튜브", "프리미어", "컷편집"],
    "사진": ["사진", "포토", "출사", "스냅"],
    "드로잉": ["드로잉", "일러스트", "미술", "스케치"],
    "수채화": ["수채화", "유화", "페인팅", "그림"],
    "캘리그라피": ["캘리그라피", "손글씨", "붓글씨"],
    "도예": ["도예", "도자기", "공방"],
    "가구공예": ["가구공예", "목공", "DIY"],
    "요리": ["요리", "쿠킹", "레시피", "셰프"],
    "베이킹": ["베이킹", "제과", "제빵", "디저트"],
    "바리스타": ["바리스타", "커피", "카페", "로스팅"],
    "조주": ["조주", "칵테일", "바텐더", "믹솔로지"],
    "와인": ["와인", "소믈리에", "빈티지"],
    "기타": ["기타", "어쿠스틱", "일렉기타"],
    "드럼": ["드럼", "타악기", "비트"],
    "첼로": ["첼로", "현악기", "클래식"],
    "플루트": ["플루트", "목관악기", "관현악"],
    "작곡": ["작곡", "미디", "편곡", "프로듀싱"],
    "독서": ["독서", "책", "북클럽", "라이브러리"],
    "글쓰기": ["글쓰기", "작법", "창작", "에세이"],
    "심리학": ["심리학", "마음건강", "상담"],
    "명상": ["명상", "마인드풀니스", "치유"],
    "재테크": ["재테크", "투자", "금융", "자산관리"],
    "주식": ["주식", "증권", "나스닥", "코스피"],
    "부동산": ["부동산", "임장", "경매", "내집마련"],
    "가상화폐": ["가상화폐", "코인", "블록체인", "비트코인"],
    "경제": ["경제", "경영", "시장분석"],
    "마케팅": ["마케팅", "광고", "홍보", "브랜딩"],
    "창업": ["창업", "스타트업", "비즈니스"],
    "자기계발": ["자기계발", "동기부여", "성공학"],
    "스피치": ["스피치", "발표", "웅변", "커뮤니케이션"],
    "리더십": ["리더십", "조직관리", "매니지먼트"],
    "정리정돈": ["정리정돈", "미니멀리즘", "수납"],
    "인테리어": ["인테리어", "집꾸미기", "셀프인테리어"],
    "원예": ["원예", "가드닝", "식집사", "플랜테리어"],
    "반려견": ["반려견", "강아지", "애견"],
    "반려묘": ["반려묘", "고양이", "애묘"],
    "여행": ["여행", "해외여행", "배낭여행", "투어"],
    "뷰티": ["뷰티", "메이크업", "화장품"],
    "패션": ["패션", "스타일", "코디", "OOTD"],
    "향수": ["향수", "조향", "프래그런스"],
    "피부관리": ["피부관리", "스킨케어", "에스테틱"],
    "타투": ["타투", "문신", "타투이스트"],
    "마술": ["마술", "매직", "마술사"],
    "체스": ["체스", "보드게임", "전략"],
    "바둑": ["바둑", "기원", "대국"],
    "애니메이션": ["애니메이션", "만화", "애니"],
    "영화": ["영화", "시네마", "무비"],
    "드라마": ["드라마", "시리즈", "정주행"],
    "뮤지컬": ["뮤지컬", "연극", "공연"],
    "전시회": ["전시회", "박물관", "큐레이터"],
    "천문학": ["천문학", "별자리", "관측", "우주"],
    "역사": ["역사", "한국사", "세계사", "사학"],
    "철학": ["철학", "인문학", "고전"],
    "법률": ["법률", "법학", "변호사"],
    "의학": ["의학", "건강정보", "해부학"],
    "건축": ["건축", "설계", "구조"],
    "수학": ["수학", "수리", "통계"],
    "물리학": ["물리학", "과학", "양자역학"],
    "화학": ["화학", "실험", "원소"],
    "생물학": ["생물학", "생태계", "유전학"],
    "환경": ["환경", "기후변화", "제로웨이스트"],
    "봉사활동": ["봉사활동", "기부", "사회공헌"],
    "정치": ["정치", "사회", "이슈"],
    "자동차": ["자동차", "드라이브", "카라이프"],
    "바이크": ["바이크", "오토바이", "라이딩"],
    "프라모델": ["프라모델", "건담", "조립"],
    "피규어": ["피규어", "수집", "컬렉션"],
    "드론": ["드론", "항공촬영", "무인기"],
    "원격조정": ["원격조정", "RC카", "무선조종"],
    "플라워아트": ["플라워아트", "꽃꽂이", "플로리스트"],
    "자수": ["자수", "뜨개질", "퀼트"],
    "가죽공예": ["가죽공예", "핸드메이드", "레더"],
    "사격": ["사격", "클레이사격", "슈팅"],
    "양궁": ["양궁", "활쏘기", "아처"],
    "펜싱": ["펜싱", "검술", "플뢰레"],
    "볼링": ["볼링", "스트라이크", "볼러"],
    "당구": ["당구", "포켓볼", "3쿠션"],
    "탁구": ["탁구", "핑퐁", "테이블테니스"],
    "배드민턴": ["배드민턴", "셔틀콕", "민턴"],
    "핸드볼": ["핸드볼", "구기종목"],
    "배구": ["배구", "스파이크", "발리볼"],
    "야구": ["야구", "베이스볼", "홈런"],
    "럭비": ["럭비", "미식축구"],
    "아이스하키": ["아이스하키", "스케이트"],
    "태권도": ["태권도", "품새", "격파"],
    "유도": ["유도", "메치기", "주짓수"],
    "복싱": ["복싱", "권투", "격투기"],
    "스페인어": ["스페인어", "spanish", "에스파뇰"],
    "프랑스어": ["프랑스어", "french", "불어"],
    "독일어": ["독일어", "german", "독어"]
}

NOISE_WORDS = {
    "리스트", "배우", "배우들", "찾아줘", "추천", "추천해줘",
    "가능한", "느낌", "스타일", "같은", "좀", "해줘", "보여줘"
}


def normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def parse_ai_query(ai_query: str) -> dict:
    q = normalize_text(ai_query)

    parsed = {
        "gender": "",
        "birth_group": "",
        "height_group": "",
        "keywords": [],
        "raw": ai_query.strip(),
    }

    if "여자" in q or "여성" in q:
        parsed["gender"] = "여자"
    elif "남자" in q or "남성" in q:
        parsed["gender"] = "남자"

    if "80년대" in q or "1980" in q:
        parsed["birth_group"] = "1980"
    elif "90년대" in q or "1990" in q:
        parsed["birth_group"] = "1990"
    elif "00년대" in q or "2000" in q:
        parsed["birth_group"] = "2000"
    elif "10년대" in q or "2010" in q:
        parsed["birth_group"] = "2010"

    if "150대" in q:
        parsed["height_group"] = "150"
    elif "160대" in q:
        parsed["height_group"] = "160"
    elif "170대" in q:
        parsed["height_group"] = "170"
    elif "180대" in q or "키 큰" in q:
        parsed["height_group"] = "180"

    cleaned = re.sub(r"[^\w\s가-힣]", " ", q)
    tokens = [t for t in cleaned.split() if t and t not in NOISE_WORDS]

    expanded = set()

    for token in tokens:
        if token in {"여자", "여성", "남자", "남성"}:
            continue
        if token in {"80년대", "90년대", "00년대", "10년대"}:
            continue
        if token in {"150대", "160대", "170대", "180대"}:
            continue

        matched = False
        for key, related in AI_KEYWORD_MAP.items():
            if token == key or token in key or key in token:
                expanded.update([normalize_text(x) for x in related])
                expanded.add(key)
                matched = True

        if not matched:
            expanded.add(token)

    parsed["keywords"] = list(expanded)
    return parsed


def actor_match_score(actor, parsed: dict) -> tuple[int, list[str]]:
    score = 0
    matched = []

    actor_gender = normalize_text(actor["gender"] if "gender" in actor.keys() else "")
    hobby = normalize_text(actor["hobby"] if "hobby" in actor.keys() else "")
    specialty = normalize_text(actor["specialty"] if "specialty" in actor.keys() else "")
    bio = normalize_text(actor["bio"] if "bio" in actor.keys() else "")
    school = normalize_text(actor["school"] if "school" in actor.keys() else "")
    name = normalize_text(actor["name"] if "name" in actor.keys() else "")

    full_text = " ".join([name, hobby, specialty, bio, school])

    if parsed["gender"]:
        if actor_gender == normalize_text(parsed["gender"]):
            score += 5
            matched.append(parsed["gender"])
        else:
            return (-999, [])

    birth_year = actor["birth_year"] if "birth_year" in actor.keys() else None
    if parsed["birth_group"] and birth_year:
        try:
            by = int(birth_year)
            if parsed["birth_group"] == "1980" and 1980 <= by <= 1989:
                score += 4
                matched.append("80년대생")
            elif parsed["birth_group"] == "1990" and 1990 <= by <= 1999:
                score += 4
                matched.append("90년대생")
            elif parsed["birth_group"] == "2000" and 2000 <= by <= 2009:
                score += 4
                matched.append("00년대생")
            elif parsed["birth_group"] == "2010" and 2010 <= by <= 2019:
                score += 4
                matched.append("10년대생")
            else:
                score -= 1
        except Exception:
            pass

    height_cm = actor["height_cm"] if "height_cm" in actor.keys() else None
    if parsed["height_group"] and height_cm:
        try:
            h = float(height_cm)
            if parsed["height_group"] == "150" and 150 <= h < 160:
                score += 3
                matched.append("150대")
            elif parsed["height_group"] == "160" and 160 <= h < 170:
                score += 3
                matched.append("160대")
            elif parsed["height_group"] == "170" and 170 <= h < 180:
                score += 3
                matched.append("170대")
            elif parsed["height_group"] == "180" and 180 <= h < 190:
                score += 3
                matched.append("180대")
        except Exception:
            pass

    for kw in parsed["keywords"]:
        kw = normalize_text(kw)
        if not kw:
            continue

        if kw in specialty:
            score += 4
            matched.append(kw)
        elif kw in hobby:
            score += 3
            matched.append(kw)
        elif kw in bio:
            score += 2
            matched.append(kw)
        elif kw in school:
            score += 1
            matched.append(kw)
        elif kw in full_text:
            score += 1
            matched.append(kw)

    return score, list(dict.fromkeys(matched))


def apply_ai_search(actors, ai_query: str):
    parsed = parse_ai_query(ai_query)
    scored = []

    for actor in actors:
        score, matched = actor_match_score(actor, parsed)
        if score > 0:
            scored.append((actor, score, matched))

    scored.sort(
        key=lambda x: (
            x[1],
            x[0]["birth_year"] if x[0]["birth_year"] else 0,
            x[0]["id"]
        ),
        reverse=True
    )

    return scored, parsed
