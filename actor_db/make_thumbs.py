import os
import uuid
import sqlite3
from PIL import Image, ImageOps

DB_PATH = "actors.db"
UPLOAD_DIR = os.path.join("static", "uploads")

def url_to_fs_path(url: str) -> str:
    return url.lstrip("/").replace("/", os.sep)

def make_thumb(image_url: str) -> str | None:
    if not image_url:
        return None

    src_path = url_to_fs_path(image_url)
    if not os.path.exists(src_path):
        return None

    try:
        with Image.open(src_path) as img:
            img = ImageOps.exif_transpose(img)

            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")

            img.thumbnail((360, 360))

            filename = f"thumb_{uuid.uuid4().hex}.jpg"
            save_path = os.path.join(UPLOAD_DIR, filename)
            img.save(save_path, format="JPEG", quality=82, optimize=True)

            return f"/static/uploads/{filename}"
    except Exception as e:
        print("thumb fail:", image_url, e)
        return None

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(actors)")
cols = [row[1] for row in cur.fetchall()]
if "photo_thumb_path" not in cols:
    cur.execute("ALTER TABLE actors ADD COLUMN photo_thumb_path TEXT")
    conn.commit()

cur.execute("""
    SELECT id, photo_path, photo_thumb_path
    FROM actors
""")
rows = cur.fetchall()

for actor_id, photo_path, photo_thumb_path in rows:
    if photo_path and not photo_thumb_path:
        thumb_url = make_thumb(photo_path)
        if thumb_url:
            cur.execute(
                "UPDATE actors SET photo_thumb_path=? WHERE id=?",
                (thumb_url, actor_id)
            )
            print("updated:", actor_id, thumb_url)

conn.commit()
conn.close()
print("done")