from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator
import os

DATABASE_URL = "postgresql+psycopg2://postgres:admin@localhost:5432/crystal_plc"

DB_STATEMENT_TIMEOUT_MS = int(
    os.getenv("DB_STATEMENT_TIMEOUT_MS", "120000")
)
DB_LOCK_TIMEOUT_MS = int(
    os.getenv("DB_LOCK_TIMEOUT_MS", "5000")
)
DB_IDLE_TX_TIMEOUT_MS = int(
    os.getenv("DB_IDLE_TX_TIMEOUT_MS", "120000")
)
DB_CONNECT_TIMEOUT_SEC = int(
    os.getenv("DB_CONNECT_TIMEOUT_SEC", "10")
)

_PG_OPTIONS = (
    f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS} "
    f"-c lock_timeout={DB_LOCK_TIMEOUT_MS} "
    f"-c idle_in_transaction_session_timeout={DB_IDLE_TX_TIMEOUT_MS}"
)

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_timeout=30,
    pool_recycle=1800,
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
