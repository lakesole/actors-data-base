"""
업로드 파일을 backend/app/static/uploads → storage/uploads 로 옮기고,
DB에 저장된 URL을 /static/uploads/... → /media/uploads/... 로 바꾼다. (Phase 4, 한 번만 실행)

사용:
    backend/.venv/bin/python scripts/migrate_uploads_to_media.py           # 미리보기만 (아무것도 바꾸지 않음)
    backend/.venv/bin/python scripts/migrate_uploads_to_media.py --apply   # 실제 실행

--apply 를 하면 먼저 DB 파일을 <DB_PATH>.bak-before-media-<시각> 으로 복사한다.
여러 번 실행해도 이미 옮긴 파일과 바뀐 URL은 건너뛴다.
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.config import DB_PATH, LEGACY_UPLOAD_DIR, UPLOAD_DIR  # noqa: E402

OLD_PREFIX = "/static/uploads/"
NEW_PREFIX = "/media/uploads/"

URL_COLUMNS = [
    ("actors", "photo_path"),
    ("actors", "photo_thumb_path"),
    ("actors", "compcard_path"),
    ("actors", "compcard_preview_path"),
    ("actors", "acting_video_path"),
    ("acting_videos", "video_path"),
]


def migrate(db_path: str, legacy_dir: Path, upload_dir: Path, apply: bool) -> dict:
    """옮길 파일 수와 바꿀 URL 수를 반환한다. apply=False면 아무것도 바꾸지 않는다."""
    legacy_dir, upload_dir = Path(legacy_dir), Path(upload_dir)
    files = sorted(p for p in legacy_dir.glob("*") if p.is_file()) if legacy_dir.exists() else []
    conflicts = [p.name for p in files if (upload_dir / p.name).exists()]

    con = sqlite3.connect(db_path)
    try:
        url_counts = {}
        for table, column in URL_COLUMNS:
            (count,) = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?", (OLD_PREFIX + "%",)
            ).fetchone()
            url_counts[f"{table}.{column}"] = count

        result = {"files": len(files), "conflicts": conflicts, "urls": url_counts, "backup": None}
        if not apply:
            return result

        if conflicts:
            raise SystemExit(f"대상 폴더에 같은 이름의 파일이 있어 중단합니다: {conflicts[:5]}")

        backup = f"{db_path}.bak-before-media-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(db_path, backup)
        result["backup"] = backup

        upload_dir.mkdir(parents=True, exist_ok=True)
        for p in files:
            shutil.move(str(p), upload_dir / p.name)

        with con:
            for table, column in URL_COLUMNS:
                con.execute(
                    f"UPDATE {table} SET {column} = ? || substr({column}, ?) WHERE {column} LIKE ?",
                    (NEW_PREFIX, len(OLD_PREFIX) + 1, OLD_PREFIX + "%"),
                )
        return result
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="실제로 파일을 옮기고 DB를 수정한다")
    args = parser.parse_args()

    print(f"DB:      {DB_PATH}")
    print(f"원래 위치: {LEGACY_UPLOAD_DIR}")
    print(f"새 위치:  {UPLOAD_DIR}")

    result = migrate(DB_PATH, LEGACY_UPLOAD_DIR, UPLOAD_DIR, args.apply)

    print(f"\n옮길 파일: {result['files']}개")
    if result["conflicts"]:
        print(f"이름이 겹치는 파일: {len(result['conflicts'])}개 {result['conflicts'][:5]}")
    print("바꿀 URL:")
    for name, count in result["urls"].items():
        print(f"  {name}: {count}개")

    if args.apply:
        print(f"\n완료. DB 백업: {result['backup']}")
    else:
        print("\n미리보기입니다. 실제로 실행하려면 --apply 를 붙이세요.")


if __name__ == "__main__":
    main()
