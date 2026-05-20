"""
yahoo.py — Yahoo Finance 備用報價來源

當 TWSE STOCK_DAY_ALL API 尚未發布今日資料（盤中常見）時使用。
回傳欄位與 twse.py 相同：{stock_id, name, volume, close_price, price_change_pct}

延遲：約 15 分鐘（Yahoo Finance 免費層）
速率：yfinance 批次請求，每分鐘一次對 Yahoo Finance 無壓力。
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# 每次最多向 Yahoo Finance 查詢的股票數（按昨日成交量排序取前 N）
# yfinance 每批次約 1500 筆，500 筆約 1-2 個 HTTP request，10-20 秒完成
_MAX_FETCH = 500


def fetch_yahoo_quotes(
    twse_records: list[dict],
    max_stocks: int = _MAX_FETCH,
) -> tuple[list[dict], str | None]:
    """
    以 Yahoo Finance 取得台股即時報價（~15 分鐘延遲）。

    Args:
        twse_records: TWSE 原始資料（即使是舊日期），用來提供股票代號與中文名稱。
                      函式僅取 stock_id / name；價格欄位不使用。
        max_stocks:   最多查詢幾檔（按 TWSE 成交量排序取前 N）。

    Returns:
        (records, trading_date_iso)
        records: list[{stock_id, name, volume, close_price, price_change_pct}]
        trading_date_iso: "2026-05-18" 格式，若無法取得則為 None
    """
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        logger.error("yfinance / pandas not installed. Add 'yfinance' to requirements.txt.")
        return [], None

    if not twse_records:
        return [], None

    # 取前 N 高成交量（昨日 TWSE 排名，作為今日盤中的優先查詢對象）
    top = sorted(twse_records, key=lambda r: r.get("volume", 0), reverse=True)[:max_stocks]
    stock_ids = [r["stock_id"] for r in top]
    name_map = {r["stock_id"]: r["name"] for r in twse_records}

    tickers = [f"{sid}.TW" for sid in stock_ids]
    logger.info("Yahoo Finance: fetching %d TWSE tickers (period=5d)...", len(tickers))

    try:
        # period="5d" interval="1d":
        #   - 取最近 5 個交易日收盤，最後一列 = 今日盤中最新價（15分鐘延遲）
        #   - 倒數第二列 = 昨日收盤，用以計算漲跌幅
        raw = yf.download(
            tickers,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )

        if raw is None or raw.empty:
            logger.warning("Yahoo Finance returned empty DataFrame")
            return [], None

        # 取最後一列的交易日期
        last_idx = raw.index[-1]
        if hasattr(last_idx, "date"):
            trading_date = last_idx.date().strftime("%Y-%m-%d")
        else:
            trading_date = str(last_idx)[:10]

        multi = isinstance(raw.columns, pd.MultiIndex)

        records: list[dict] = []
        for sid, ticker in zip(stock_ids, tickers):
            try:
                if multi:
                    close_s = raw["Close"][ticker].dropna()
                    vol_s   = raw["Volume"][ticker].dropna()
                else:
                    close_s = raw["Close"].dropna()
                    vol_s   = raw["Volume"].dropna()

                if close_s.empty:
                    continue

                close_today  = float(close_s.iloc[-1])
                volume_today = int(vol_s.iloc[-1]) if not vol_s.empty else 0

                if math.isnan(close_today) or close_today <= 0:
                    continue

                if len(close_s) >= 2:
                    close_prev = float(close_s.iloc[-2])
                    pct = (close_today - close_prev) / close_prev * 100 if close_prev else 0.0
                else:
                    pct = 0.0

                records.append({
                    "stock_id": sid,
                    "name":     name_map.get(sid, sid),
                    "volume":   volume_today,
                    "close_price":      round(close_today, 2),
                    "price_change_pct": round(pct, 2),
                })
            except (KeyError, IndexError, TypeError, ValueError):
                continue

        logger.info(
            "Yahoo Finance: %d/%d records fetched, trading_date=%s",
            len(records), len(tickers), trading_date,
        )
        return records, trading_date

    except Exception as exc:
        logger.error("Yahoo Finance fetch failed: %s", exc)
        return [], None
