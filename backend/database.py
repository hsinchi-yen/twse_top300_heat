import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/twse_heat.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """
    Embedded-friendly SQLite defaults:
    - WAL: better read/write concurrency for API + crawler.
    - NORMAL sync: balanced durability/performance for dashboard workloads.
    - busy_timeout: avoid transient lock errors under concurrent access.
    """
    cursor = dbapi_connection.cursor()
    busy_timeout_ms = os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000")
    cache_kib = os.getenv("SQLITE_CACHE_SIZE_KIB", "8192")
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA temp_store=MEMORY;")
    cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)};")
    # SQLite expects negative cache_size to mean kibibytes.
    cursor.execute(f"PRAGMA cache_size={-abs(int(cache_kib))};")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
