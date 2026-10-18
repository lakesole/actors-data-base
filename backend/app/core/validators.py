import re
from datetime import datetime, timedelta

from fastapi import HTTPException


def validate_yyyy_mm_dd(date_str: str) -> str:
    if not date_str:
        raise HTTPException(status_code=400, detail="날짜가 비어 있습니다.")

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        raise HTTPException(status_code=400, detail="날짜 형식은 YYYY-MM-DD 이어야 합니다.")

    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="올바른 날짜가 아닙니다.")

    year = parsed.year
    if year < 1900 or year > 2099:
        raise HTTPException(status_code=400, detail="연도는 1900~2099 사이의 4자리만 가능합니다.")

    return date_str


def clean_birth_year(value) -> int | None:
    if value is None:
        return None
    s = digits_only(value, 4)
    if len(s) != 4:
        return None
    return int(s)


def clean_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()

    if len(value) >= 10:
        value = value[:10]

    # YYYY-MM-DD만 허용
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None

    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def default_contract_end_date(contract_date: str) -> str | None:
    """계약 시작일 기준 1년 뒤 전날. 2024-03-01 → 2025-02-28"""
    try:
        start_date = datetime.strptime(contract_date, "%Y-%m-%d")
        next_year = start_date.replace(year=start_date.year + 1)
        return (next_year - timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def digits_only(value, limit: int | None = None) -> str:
    """숫자만 남긴다. limit이 있으면 앞에서부터 그 길이만큼 자른다."""
    digits = "".join(ch for ch in str(value or "").strip() if ch.isdigit())
    return digits[:limit] if limit is not None else digits


def parse_optional_float(value) -> float | None:
    try:
        return float(value) if str(value).strip() else None
    except Exception:
        return None


def parse_optional_int(value) -> int | None:
    if not str(value).strip():
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def now_str() -> str:
    """DB에 저장하는 일반 시각 형식 (YYYY-MM-DD HH:MM:SS)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_iso() -> str:
    """기록류(created_at)에 저장하는 ISO 형식 (YYYY-MM-DDTHH:MM:SS)."""
    return datetime.now().isoformat(timespec="seconds")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")
