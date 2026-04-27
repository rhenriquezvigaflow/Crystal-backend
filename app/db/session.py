from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

DB_STATEMENT_TIMEOUT_MS = settings.DB_STATEMENT_TIMEOUT_MS
DB_LOCK_TIMEOUT_MS = settings.DB_LOCK_TIMEOUT_MS
DB_IDLE_TX_TIMEOUT_MS = settings.DB_IDLE_TX_TIMEOUT_MS
DB_CONNECT_TIMEOUT_SEC = settings.DB_CONNECT_TIMEOUT_SEC

_PG_OPTIONS = (
    f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS} "
    f"-c lock_timeout={DB_LOCK_TIMEOUT_MS} "
    f"-c idle_in_transaction_session_timeout={DB_IDLE_TX_TIMEOUT_MS}"
)

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_timeout=settings.DB_POOL_TIMEOUT_SEC,
    pool_recycle=settings.DB_POOL_RECYCLE_SEC,
    connect_args={
        "options": _PG_OPTIONS,
        "connect_timeout": DB_CONNECT_TIMEOUT_SEC,
    },
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)



def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
