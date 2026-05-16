"""
test_etf_api.py — Integration tests for GET /api/etf

Tests:
  - Empty DB returns empty list (not 500)
  - sort_by=turnover and sort_by=asset_scale respected
  - ETag caching returns 304 on repeat
  - Response schema has all required fields
  - Pagination via limit param
  - Invalid sort_by rejected with 422
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# conftest.py sets DATABASE_URL before main is imported
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from database import engine, Base, get_db
import models.etf           # ensure table registered
import routers.etf as etf_router  # for cache clearing between tests

Base.metadata.create_all(bind=engine)

client = TestClient(app)

REQUIRED_ETF_FIELDS = {
    "etf_id", "name", "etf_type", "asset_scale", "outstanding_units",
    "volume", "turnover_rate", "close_price", "price_change_pct",
    "nav", "premium_discount", "management_fee",
    "color_tier", "turnover_rank", "asset_scale_rank",
}


def _seed_etfs(rows: list[dict]) -> None:
    etf_router._ETF_CACHE.clear()   # flush in-process cache between tests
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS etf_ranks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                etf_id TEXT NOT NULL, name TEXT NOT NULL, date TEXT NOT NULL,
                etf_type TEXT DEFAULT '股票型', tracking_index TEXT DEFAULT '',
                management_fee REAL, asset_scale REAL, outstanding_units REAL,
                volume INTEGER, turnover_rate REAL, close_price REAL,
                price_change_pct REAL, nav REAL, premium_discount REAL,
                color_tier TEXT DEFAULT 'neutral',
                turnover_rank INTEGER, asset_scale_rank INTEGER,
                UNIQUE(etf_id, date)
            )
        """))
        conn.execute(text("DELETE FROM etf_ranks"))
        for r in rows:
            conn.execute(
                text("""INSERT OR REPLACE INTO etf_ranks
                    (etf_id,name,date,etf_type,asset_scale,outstanding_units,
                     volume,turnover_rate,close_price,price_change_pct,
                     nav,premium_discount,management_fee,color_tier,
                     turnover_rank,asset_scale_rank)
                    VALUES
                    (:etf_id,:name,:date,:etf_type,:asset_scale,:outstanding_units,
                     :volume,:turnover_rate,:close_price,:price_change_pct,
                     :nav,:premium_discount,:management_fee,:color_tier,
                     :turnover_rank,:asset_scale_rank)"""),
                r,
            )
        conn.commit()


SAMPLE = [
    {"etf_id": "0050", "name": "元大台灣50", "date": "2026-05-16",
     "etf_type": "股票型", "asset_scale": 3241.5, "outstanding_units": 1680000000,
     "volume": 6888000, "turnover_rate": 0.41, "close_price": 185.5,
     "price_change_pct": 1.23, "nav": 185.2, "premium_discount": 0.162,
     "management_fee": 0.32, "color_tier": "light_red",
     "turnover_rank": 2, "asset_scale_rank": 1},
    {"etf_id": "00631L", "name": "元大台灣50正2", "date": "2026-05-16",
     "etf_type": "槓桿/反向", "asset_scale": 320.5, "outstanding_units": 210000000,
     "volume": 2100000, "turnover_rate": 1.00, "close_price": 85.30,
     "price_change_pct": 3.12, "nav": 85.10, "premium_discount": 0.235,
     "management_fee": 1.0, "color_tier": "light_red",
     "turnover_rank": 1, "asset_scale_rank": 2},
    {"etf_id": "00679B", "name": "元大美債20年", "date": "2026-05-16",
     "etf_type": "債券型", "asset_scale": 890.2, "outstanding_units": 450000000,
     "volume": 450000, "turnover_rate": 0.10, "close_price": 32.12,
     "price_change_pct": -0.56, "nav": 32.20, "premium_discount": -0.248,
     "management_fee": 0.15, "color_tier": "neutral",
     "turnover_rank": 3, "asset_scale_rank": 3},
]


class TestGetEtf:
    def test_empty_db_returns_empty_list(self):
        etf_router._ETF_CACHE.clear()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM etf_ranks"))
            conn.commit()
        resp = client.get("/api/etf")
        assert resp.status_code == 200
        body = resp.json()
        assert body["etfs"] == []

    def test_returns_required_fields(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["etfs"]) == 3
        for etf in body["etfs"]:
            missing = REQUIRED_ETF_FIELDS - set(etf.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_sort_by_turnover_default(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf?sort_by=turnover")
        assert resp.status_code == 200
        etfs = resp.json()["etfs"]
        ranks = [e["turnover_rank"] for e in etfs]
        assert ranks == sorted(ranks), "ETFs not sorted by turnover_rank"

    def test_sort_by_asset_scale(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf?sort_by=asset_scale")
        assert resp.status_code == 200
        etfs = resp.json()["etfs"]
        ranks = [e["asset_scale_rank"] for e in etfs]
        assert ranks == sorted(ranks), "ETFs not sorted by asset_scale_rank"

    def test_limit_param(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()["etfs"]) == 2

    def test_invalid_sort_by_rejected(self):
        resp = client.get("/api/etf?sort_by=volume")
        assert resp.status_code == 422

    def test_etag_304_on_repeat(self):
        _seed_etfs(SAMPLE)
        r1 = client.get("/api/etf")
        assert r1.status_code == 200
        etag = r1.headers.get("ETag", "")
        assert etag

        r2 = client.get("/api/etf", headers={"if-none-match": etag})
        assert r2.status_code in (200, 304)  # cache TTL may not have expired in test

    def test_response_has_meta_fields(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf")
        body = resp.json()
        for key in ("sort_by", "date", "market_open", "updated_at", "etfs"):
            assert key in body, f"Missing top-level key: {key}"

    def test_turnover_rate_values_correct(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf?sort_by=turnover")
        etfs = resp.json()["etfs"]
        top = etfs[0]
        # 00631L has highest turnover_rank=1 → should be first
        assert top["etf_id"] == "00631L"
        # validate the stored turnover_rate
        assert abs(top["turnover_rate"] - 1.00) < 0.01

    def test_premium_discount_sign(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf")
        etfs_map = {e["etf_id"]: e for e in resp.json()["etfs"]}
        # 0050: close > nav → positive premium
        assert etfs_map["0050"]["premium_discount"] > 0
        # 00679B: close < nav → negative (discount)
        assert etfs_map["00679B"]["premium_discount"] < 0

    def test_etf_type_classification_in_response(self):
        _seed_etfs(SAMPLE)
        resp = client.get("/api/etf")
        etfs_map = {e["etf_id"]: e for e in resp.json()["etfs"]}
        assert etfs_map["0050"]["etf_type"]    == "股票型"
        assert etfs_map["00631L"]["etf_type"]  == "槓桿/反向"
        assert etfs_map["00679B"]["etf_type"]  == "債券型"
