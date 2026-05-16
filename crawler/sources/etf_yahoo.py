"""
etf_yahoo.py — Yahoo Finance TW ETF asset scale scraper

Scrapes https://tw.stock.yahoo.com/tw-etf/total-assets for the top 100 ETF
total assets (資產規模) in NT億.

Yahoo renders this page via XHR. We try two approaches:
  1. Undocumented Yahoo Finance screener API (JSON, preferred)
  2. HTML fallback with BeautifulSoup

Returns: {etf_id: asset_scale_億} dict
"""

from __future__ import annotations
import logging
import random
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# Yahoo Finance TW internal screener endpoint (observed via DevTools)
_YAHOO_SCREENER_URL = (
    "https://tw.stock.yahoo.com/v2/finance/screener"
    "?lang=zh-TW&region=TW&scrIds=etf_by_assets&count=100&start=0"
)

# Fallback: static page (requires BeautifulSoup)
_YAHOO_PAGE_URL = "https://tw.stock.yahoo.com/tw-etf/total-assets"


def _headers() -> dict:
    return {
        "User-Agent": random.choice(_UA_POOL),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": "https://tw.stock.yahoo.com/tw-etf/total-assets",
    }


def _get(url: str, timeout: int = 20) -> requests.Response | None:
    time.sleep(random.uniform(1.5, 3.0))
    try:
        resp = requests.get(url, headers=_headers(), timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as exc:
        logger.warning("Yahoo GET failed url=%s: %s", url, exc)
        return None


def _parse_screener_json(data: Any) -> dict[str, float]:
    """Parse Yahoo Finance screener JSON response."""
    asset_map: dict[str, float] = {}
    try:
        quotes = (
            data.get("finance", {})
                .get("result", [{}])[0]
                .get("quotes", [])
        )
        for q in quotes:
            symbol = str(q.get("symbol", "")).replace(".TW", "").strip()
            # totalAssets in NT$, divide by 1e8 to get 億
            total_assets = q.get("totalAssets") or q.get("fundInceptionDate")
            if total_assets is None:
                continue
            if isinstance(total_assets, (int, float)) and total_assets > 0:
                asset_map[symbol] = round(total_assets / 1e8, 2)
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Yahoo screener JSON parse error: %s", exc)
    return asset_map


def _parse_html_table(html: str) -> dict[str, float]:
    """Fallback: parse HTML table with BeautifulSoup."""
    asset_map: dict[str, float] = {}
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table tbody tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            # typical column order: rank | name/code | ... | total_assets
            # extract ticker from first or second cell
            ticker_cell = cells[1].get_text(strip=True)
            # find 4-6 char alphanumeric ticker (e.g. 0050, 00878, 00981A)
            import re
            match = re.search(r'\b(0\d{3,5}[A-Z]?)\b', ticker_cell)
            if not match:
                match = re.search(r'\b(\d{6}[A-Z]?)\b', ticker_cell)
            if not match:
                continue
            etf_id = match.group(1)
            # asset scale typically last or near-last column, in NT億 or NT萬
            for cell in reversed(cells):
                text = cell.get_text(strip=True).replace(",", "")
                try:
                    val = float(text)
                    if val > 0:
                        asset_map[etf_id] = round(val, 2)
                        break
                except ValueError:
                    continue
    except ImportError:
        logger.warning("BeautifulSoup not installed; HTML fallback unavailable")
    except Exception as exc:
        logger.warning("Yahoo HTML parse error: %s", exc)
    return asset_map


def fetch_etf_asset_scale() -> dict[str, float]:
    """
    Returns {etf_id: asset_scale_億} for up to 100 ETFs.
    Tries JSON screener first, falls back to HTML parsing.
    Returns empty dict on complete failure (caller should use cached/zero values).
    """
    # Attempt 1: screener JSON API
    resp = _get(_YAHOO_SCREENER_URL)
    if resp is not None:
        try:
            data = resp.json()
            result = _parse_screener_json(data)
            if result:
                logger.info("Yahoo ETF asset scale via JSON: %d records", len(result))
                return result
        except Exception as exc:
            logger.warning("Yahoo screener JSON decode failed: %s", exc)

    # Attempt 2: HTML page
    time.sleep(random.uniform(2.0, 4.0))
    resp = _get(_YAHOO_PAGE_URL)
    if resp is not None:
        result = _parse_html_table(resp.text)
        if result:
            logger.info("Yahoo ETF asset scale via HTML: %d records", len(result))
            return result

    logger.error("Yahoo ETF asset scale fetch failed (all methods exhausted)")
    return {}
