"""
rate_limit_probe.py — StockAnalysisDashBoard buy_score API 限流邊界測試

量測三件事：
  1. 需要連續多少次請求才觸發限流（threshold）
  2. 被限流後多久才恢復（recovery_s）
  3. 間歇性限流模式：成功→失敗→成功的模式下的失敗率

用法：
  pip install requests tabulate
  python tools/rate_limit_probe.py --url http://10.1.1.230:18000 --token YOUR_TOKEN

  # 只跑特定測試
  python tools/rate_limit_probe.py --url http://10.1.1.230:18000 --token YOUR_TOKEN --test threshold
  python tools/rate_limit_probe.py --url http://10.1.1.230:18000 --token YOUR_TOKEN --test recovery
  python tools/rate_limit_probe.py --url http://10.1.1.230:18000 --token YOUR_TOKEN --test pattern
"""

import argparse
import time
import statistics
from datetime import datetime

try:
    import requests
    from tabulate import tabulate
except ImportError:
    print("請先安裝依賴：pip install requests tabulate")
    raise

# 使用成交量最高的幾支穩定股票做測試
TEST_STOCKS = [
    "2330", "2317", "2454", "2382", "2308",
    "3711", "2303", "2379", "6770", "3034",
    "2344", "2337", "5347", "2408", "6488",
]


def make_request(url: str, stock_id: str, token: str, timeout: float = 10.0):
    """回傳 (status_code, elapsed_ms, error_msg)"""
    headers = {"X-FinMind-Token": token} if token else {}
    endpoint = f"{url}/api/stocks/{stock_id}/buy_score"
    t0 = time.perf_counter()
    try:
        resp = requests.get(endpoint, headers=headers, timeout=timeout)
        elapsed = (time.perf_counter() - t0) * 1000
        return resp.status_code, elapsed, None
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return 0, elapsed, str(e)


def test_threshold(url: str, token: str, max_burst: int = 30) -> dict:
    """
    測試一：快速連發請求，找出觸發限流的臨界點。
    0 delay → 直到看到非 200 回應為止。
    """
    print("\n=== 測試一：限流觸發閾值 ===")
    print(f"對同一股票連發請求（無間隔），最多 {max_burst} 次...")

    results = []
    first_fail_at = None
    stock_id = TEST_STOCKS[0]

    for i in range(1, max_burst + 1):
        code, ms, err = make_request(url, stock_id, token)
        status = "OK" if code == 200 else f"FAIL({code})"
        results.append({"req": i, "status": code, "ms": round(ms), "err": err})
        print(f"  #{i:2d}  {status:12s}  {ms:6.0f}ms")

        if code != 200 and first_fail_at is None:
            first_fail_at = i

        # 連續 3 次失敗就停止，避免過度打 API
        consecutive_fails = sum(1 for r in results[-3:] if r["status"] != 200)
        if consecutive_fails >= 3:
            print(f"  → 連續 3 次失敗，停止測試")
            break

    if first_fail_at:
        print(f"\n結果：第 {first_fail_at} 次請求開始出現失敗")
    else:
        print(f"\n結果：連發 {len(results)} 次均未觸發限流")

    return {"first_fail_at": first_fail_at, "total_sent": len(results), "results": results}


def test_recovery(url: str, token: str, probe_max_s: int = 300) -> dict:
    """
    測試二：先觸發限流，然後每隔一段時間探測是否恢復。
    回傳恢復所需的秒數。
    """
    print("\n=== 測試二：限流恢復時間 ===")

    # 先快速打到觸發限流
    print("先觸發限流...")
    stock_id = TEST_STOCKS[0]
    triggered = False
    for i in range(20):
        code, ms, _ = make_request(url, stock_id, token)
        if code != 200:
            triggered = True
            print(f"  第 {i+1} 次出現非 200（{code}），開始計時恢復...")
            break
        time.sleep(0.05)

    if not triggered:
        print("  無法觸發限流（可能無速率限制），跳過此測試")
        return {"triggered": False, "recovery_s": None}

    # 探測恢復（指數間隔：5s, 10s, 20s, 30s, 60s, 120s, ...）
    t_fail = time.perf_counter()
    probe_intervals = [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300]
    probed_at = 0

    for wait in probe_intervals:
        remaining = wait - probed_at
        if remaining > 0:
            print(f"  等待 {remaining}s...")
            time.sleep(remaining)
        probed_at = wait

        elapsed = time.perf_counter() - t_fail
        # 連發 3 次確認真的恢復
        successes = 0
        for sid in TEST_STOCKS[:3]:
            code, ms, _ = make_request(url, sid, token)
            if code == 200:
                successes += 1
            time.sleep(0.2)

        print(f"  {elapsed:5.0f}s 後探測：{successes}/3 成功")

        if successes >= 2:
            print(f"\n結果：限流後約 {elapsed:.0f}s 恢復（在 {wait}s 探測點確認）")
            return {"triggered": True, "recovery_s": elapsed, "confirmed_at_interval": wait}

        if elapsed > probe_max_s:
            break

    print(f"\n結果：{probe_max_s}s 內未觀察到恢復")
    return {"triggered": True, "recovery_s": None, "timeout_s": probe_max_s}


def test_pattern(url: str, token: str, delay_s: float = 1.2, count: int = 30) -> dict:
    """
    測試三：模擬正常爬取節奏（1.2s 間隔），觀察失敗率與分布。
    這是最接近實際運行的測試。
    """
    print(f"\n=== 測試三：正常爬取節奏（{delay_s}s 間隔，共 {count} 支）===")

    results = []
    stocks = (TEST_STOCKS * ((count // len(TEST_STOCKS)) + 1))[:count]

    for i, sid in enumerate(stocks):
        code, ms, err = make_request(url, sid, token)
        ok = code == 200
        results.append({"i": i + 1, "sid": sid, "code": code, "ms": ms, "ok": ok})
        status = "✓" if ok else f"✗({code})"
        print(f"  [{i+1:2d}/{count}] {sid}  {status}  {ms:.0f}ms")

        if i < count - 1:
            time.sleep(delay_s)

    success_count = sum(1 for r in results if r["ok"])
    fail_indices = [r["i"] for r in results if not r["ok"]]
    latencies = [r["ms"] for r in results if r["ok"]]

    print(f"\n結果：成功 {success_count}/{count}（{success_count/count*100:.1f}%）")
    if fail_indices:
        print(f"  失敗位置：{fail_indices}")
    if latencies:
        print(f"  成功請求延遲：avg={statistics.mean(latencies):.0f}ms  "
              f"p95={sorted(latencies)[int(len(latencies)*0.95)]:.0f}ms  "
              f"max={max(latencies):.0f}ms")

    # 分析連續失敗模式
    consecutive = 0
    max_consecutive = 0
    for r in results:
        if not r["ok"]:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    print(f"  最長連續失敗：{max_consecutive} 次")

    return {
        "success_rate": success_count / count,
        "fail_indices": fail_indices,
        "max_consecutive_fails": max_consecutive,
        "avg_latency_ms": statistics.mean(latencies) if latencies else None,
    }


def main():
    parser = argparse.ArgumentParser(description="StockAnalysisDashBoard 限流邊界測試")
    parser.add_argument("--url", default="http://localhost:18000", help="StockAnalysisDashBoard base URL")
    parser.add_argument("--token", default="", help="FinMind token (X-FinMind-Token header)")
    parser.add_argument(
        "--test",
        choices=["threshold", "recovery", "pattern", "all"],
        default="all",
        help="要跑哪個測試（預設全跑）",
    )
    args = parser.parse_args()

    print(f"目標 URL：{args.url}")
    print(f"Token：{'(已設定)' if args.token else '(未設定)'}")
    print(f"開始時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 先確認連線
    print("\n確認連線...")
    code, ms, err = make_request(args.url, TEST_STOCKS[0], args.token)
    if code == 0:
        print(f"  ✗ 無法連線：{err}")
        return
    print(f"  ✓ 連線成功（{code}，{ms:.0f}ms）")

    summary = {}

    if args.test in ("threshold", "all"):
        summary["threshold"] = test_threshold(args.url, args.token)

    if args.test in ("recovery", "all"):
        summary["recovery"] = test_recovery(args.url, args.token)

    if args.test in ("pattern", "all"):
        summary["pattern"] = test_pattern(args.url, args.token)

    # 建議
    print("\n" + "=" * 50)
    print("建議參數：")
    t = summary.get("threshold", {})
    r = summary.get("recovery", {})
    p = summary.get("pattern", {})

    threshold = t.get("first_fail_at")
    recovery_s = r.get("recovery_s")

    if threshold is None:
        print("  → 未觀察到限流，可考慮縮短 REQUEST_DELAY 或使用預設值 1.2s")
    else:
        print(f"  → 連發 {threshold} 次觸發限流")
        if recovery_s:
            print(f"  → 恢復時間約 {recovery_s:.0f}s")
            recommended_wait = int(recovery_s * 1.3)  # 加 30% 緩衝
            print(f"  → 建議 RATE_LIMIT_BASE_WAIT_S = {recommended_wait}（恢復時間 × 1.3 緩衝）")
        else:
            print("  → 恢復時間未知，建議維持預設 900s")

    max_consec = p.get("max_consecutive_fails", 0)
    if max_consec > 0:
        print(f"  → 正常節奏下最長連續失敗 {max_consec} 次，")
        if max_consec < 5:
            print(f"     目前閾值 5 可能太高（間歇失敗會被忽略），建議改為 {max(2, max_consec - 1)}")
        else:
            print(f"     閾值 5 合理")


if __name__ == "__main__":
    main()
