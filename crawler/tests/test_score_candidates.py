"""
test_score_candidates.py — buy-score candidate pool = volume pool ∪ watchlist.
"""

import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# main.py imports apscheduler at module load; it is only installed in the crawler
# container. Skip cleanly when running outside that environment.
pytest.importorskip("apscheduler")

import main


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE stock_ranks (stock_id TEXT, date TEXT, volume INTEGER, volume_rank INTEGER)
        """))
        for sid, rank in [("2330", 1), ("2317", 2), ("2454", 3), ("6488", 650)]:
            conn.execute(text(
                "INSERT INTO stock_ranks VALUES (:s, '2026-10-23', 1000, :r)"
            ), {"s": sid, "r": rank})
    with sessionmaker(bind=engine)() as s:
        yield s


def _create_watchlist(session, ids):
    session.execute(text("CREATE TABLE watchlist (stock_id TEXT PRIMARY KEY, note TEXT, added_at TEXT)"))
    for i, sid in enumerate(ids):
        session.execute(text(
            "INSERT INTO watchlist VALUES (:s, '', :t)"
        ), {"s": sid, "t": f"2026-10-0{i + 1}T00:00:00+08:00"})
    session.commit()


def test_pool_only_when_no_watchlist_table(session, monkeypatch):
    monkeypatch.setattr(main, "SCORE_CANDIDATE_LIMIT", 2)
    assert main._score_candidates(session, "2026-10-23") == ["2330", "2317"]


def test_watchlist_outside_pool_is_appended(session, monkeypatch):
    monkeypatch.setattr(main, "SCORE_CANDIDATE_LIMIT", 2)
    _create_watchlist(session, ["6488", "2330"])
    # 2330 already in the pool → not duplicated; 6488 appended after the pool.
    assert main._score_candidates(session, "2026-10-23") == ["2330", "2317", "6488"]


def test_watchlist_order_follows_added_at(session, monkeypatch):
    monkeypatch.setattr(main, "SCORE_CANDIDATE_LIMIT", 1)
    _create_watchlist(session, ["6488", "2454"])
    assert main._score_candidates(session, "2026-10-23") == ["2330", "6488", "2454"]
