import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text as _text
from database import engine, Base
from routers import stocks, sectors, etf, scores
import models.etf  # ensure ETFRank table is registered with Base

Base.metadata.create_all(bind=engine)

# Safe schema migration: add columns introduced after initial deployment
def _migrate_db() -> None:
    with engine.connect() as conn:
        for col_ddl in [
            "ALTER TABLE etf_ranks ADD COLUMN portfolio_turnover REAL",
        ]:
            try:
                conn.execute(_text(col_ddl))
                conn.commit()
            except Exception:
                pass  # column already exists

_migrate_db()

app = FastAPI(title="TWSE Top 100 Heatmap API", version="1.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("access-monitor")

ALERT_WINDOW_SECONDS = int(os.getenv("ALERT_WINDOW_SECONDS", "30"))
ALERT_MAX_REQUESTS = int(os.getenv("ALERT_MAX_REQUESTS", "40"))
_ip_hits: dict[str, deque[float]] = defaultdict(deque)
_last_alert_at: dict[str, float] = {}

_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = (
    [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
    if _allowed_origins_env
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_frequency_monitor(request: Request, call_next):
    path = request.url.path
    if path != "/health":
        xff = request.headers.get("x-forwarded-for", "")
        ip = (xff.split(",")[0].strip() if xff else "") or (
            request.client.host if request.client else "unknown"
        )

        now = time.time()
        hits = _ip_hits[ip]
        hits.append(now)
        cutoff = now - ALERT_WINDOW_SECONDS
        while hits and hits[0] < cutoff:
            hits.popleft()

        if len(hits) >= ALERT_MAX_REQUESTS:
            prev_alert = _last_alert_at.get(ip, 0.0)
            if now - prev_alert >= ALERT_WINDOW_SECONDS:
                logger.warning(
                    "High request rate detected ip=%s count=%d window_sec=%d path=%s",
                    ip,
                    len(hits),
                    ALERT_WINDOW_SECONDS,
                    path,
                )
                _last_alert_at[ip] = now

    return await call_next(request)

app.include_router(stocks.router, prefix="/api")
app.include_router(sectors.router, prefix="/api")
app.include_router(etf.router, prefix="/api")
app.include_router(scores.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
