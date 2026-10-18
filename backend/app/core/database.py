from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.core.config import DB_PATH


async def connect() -> aiosqlite.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


@asynccontextmanager
async def open_db():
    db = await connect()
    try:
        yield db
    finally:
        await db.close()


async def get_db():
    """요청마다 연결 하나를 열고 응답 후 닫는 FastAPI 의존성."""
    async with open_db() as db:
        yield db


@asynccontextmanager
async def transaction(db: aiosqlite.Connection):
    """블록이 끝나면 commit, 예외가 나면 rollback 한다. commit은 service에서만 일어난다."""
    try:
        yield db
        await db.commit()
    except BaseException:
        await db.rollback()
        raise
