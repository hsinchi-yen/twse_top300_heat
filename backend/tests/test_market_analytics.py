"""
test_market_analytics.py — pure breadth / sector / setup-validation logic.

The properties that matter most for a decision tool are asserted directly:
no look-ahead, corporate actions don't masquerade as returns, and thin data
yields null rather than a number.
"""

from datetime import date, timedelta

import pytest

from services import market_analytics as ma


def calendar(n, start=date(2025, 1, 1)):
    """n weekday dates, ascending."""
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def bars(closes, volumes=None, dates=None):
    dates = dates or calendar(len(closes))
    volumes = volumes or [1000] * len(closes)
    return list(zip(dates, closes, volumes))


class TestMovingAverage:
    def test_null_until_window_is_full(self):
        assert ma.moving_average([1.0, 2.0, 3.0, 4.0], 3) == [None, None, 2.0, 3.0]

    def test_shorter_than_window_is_all_null(self):
        assert ma.moving_average([1.0, 2.0], 3) == [None, None]

    def test_rounds_to_two_decimals(self):
        assert ma.moving_average([1.0, 1.0, 2.0], 3)[-1] == 1.33

    def test_empty(self):
        assert ma.moving_average([], 5) == []


class TestBreadth:
    def test_counts_advancers_decliners_unchanged(self):
        days = calendar(2)
        data = {
            "A": bars([100, 101], dates=days),
            "B": bars([100, 99], dates=days),
            "C": bars([100, 100], dates=days),
        }
        last = ma.breadth_series(data, 2)[-1]
        assert (last["advancers"], last["decliners"], last["unchanged"]) == (1, 1, 1)

    def test_pct_above_ma_is_null_below_minimum_sample(self):
        days = calendar(25)
        data = {f"S{i}": bars([100 + j for j in range(25)], dates=days) for i in range(5)}
        assert ma.breadth_series(data, 5)[-1]["pct_above_ma20"] is None

    def test_pct_above_ma_measures_only_qualifying_stocks(self):
        days = calendar(25)
        rising = [100 + j for j in range(25)]
        falling = [200 - j for j in range(25)]
        data = {f"U{i}": bars(rising, dates=days) for i in range(15)}
        data.update({f"D{i}": bars(falling, dates=days) for i in range(5)})
        data["SHORT"] = bars([50.0], dates=days[-1:])
        last = ma.breadth_series(data, 5)[-1]
        assert last["pct_above_ma20"] == 75.0
        assert last["pct_above_ma60"] is None

    def test_ew_index_rebases_to_100_and_chains(self):
        days = calendar(3)
        data = {f"S{i}": bars([100, 110, 121], dates=days) for i in range(2)}
        series = ma.breadth_series(data, 3)
        assert series[0]["ew_index"] == 100.0
        assert series[1]["ew_index"] == pytest.approx(110.0)
        assert series[2]["ew_index"] == pytest.approx(121.0)

    def test_corporate_action_is_not_a_return(self):
        days = calendar(2)
        data = {
            "SPLIT": bars([1000, 100], dates=days),
            "A": bars([100, 101], dates=days),
        }
        last = ma.breadth_series(data, 2)[-1]
        assert last["decliners"] == 0
        assert last["ew_index"] == pytest.approx(101.0)   # A only

    def test_gap_day_is_not_compared_across_a_suspension(self):
        days = calendar(3)
        data = {
            "SUSP": bars([100, 120], dates=[days[0], days[2]]),
            "A": bars([100, 100, 101], dates=days),
        }
        last = ma.breadth_series(data, 3)[-1]
        assert last["advancers"] == 1

    def test_ascending_and_limited_to_requested_days(self):
        days = calendar(10)
        series = ma.breadth_series({"A": bars(list(range(100, 110)), dates=days)}, 4)
        assert [p["date"] for p in series] == days[-4:]

    def test_empty(self):
        assert ma.breadth_series({}, 10) == []


class TestSectorRotation:
    def setup_method(self):
        self.days = calendar(61)
        rising = [100 * (1 + 0.001 * j) for j in range(61)]
        self.bars = {f"S{i}": bars(rising, dates=self.days) for i in range(3)}
        self.sectors = {"S0": "半導體", "S1": "半導體", "S2": "半導體"}

    def test_median_return_per_window(self):
        out = ma.sector_rotation(self.bars, self.sectors, {})
        assert out[0]["name"] == "半導體"
        assert out[0]["count"] == 3
        assert out[0]["ret_5d"] == pytest.approx(0.47, abs=0.01)
        assert out[0]["ret_60d"] == pytest.approx(6.0, abs=0.01)

    def test_median_ignores_a_single_outlier(self):
        self.bars["S2"] = bars([100] * 60 + [109], dates=self.days)
        assert ma.sector_rotation(self.bars, self.sectors, {})[0]["ret_5d"] == pytest.approx(0.47, abs=0.01)

    def test_sector_with_fewer_than_three_stocks_is_omitted(self):
        out = ma.sector_rotation({"A": self.bars["S0"], "B": self.bars["S1"]}, {"A": "X", "B": "X"}, {})
        assert out == []

    def test_other_bucket_is_omitted(self):
        assert ma.sector_rotation(self.bars, {k: "其他" for k in self.bars}, {}) == []

    def test_unmapped_stock_goes_to_other(self):
        assert ma.sector_rotation(self.bars, {}, {}) == []

    def test_short_history_gives_null_return(self):
        days = calendar(4)
        data = {f"S{i}": bars([100, 101, 102, 103], dates=days) for i in range(3)}
        row = ma.sector_rotation(data, {k: "X" for k in data}, {})[0]
        assert row["ret_5d"] is None and row["ret_20d"] is None

    def test_sorted_by_20d_with_nulls_last(self):
        days = calendar(30)
        hot = [100 + j for j in range(30)]
        cold = [200 - j for j in range(30)]
        data = {}
        sectors = {}
        for i in range(3):
            data[f"H{i}"], sectors[f"H{i}"] = bars(hot, dates=days), "熱"
            data[f"C{i}"], sectors[f"C{i}"] = bars(cold, dates=days), "冷"
            data[f"N{i}"], sectors[f"N{i}"] = bars([10, 11], dates=days[-2:]), "新"
        assert [r["name"] for r in ma.sector_rotation(data, sectors, {})] == ["熱", "冷", "新"]

    def test_inst_net_sums_last_five_flow_dates(self):
        flow_days = calendar(6)
        flows = {"S0": [(d, 10) for d in flow_days], "S1": [(flow_days[-1], 5)]}
        row = ma.sector_rotation(self.bars, self.sectors, flows)[0]
        assert row["inst_net_5d"] == 55

    def test_inst_net_null_without_flows(self):
        assert ma.sector_rotation(self.bars, self.sectors, {})[0]["inst_net_5d"] is None

    def test_window_is_market_days_not_the_stocks_own_bars(self):
        """A stock that left and re-entered the universe must not stretch '5 日'."""
        days = calendar(30)
        gappy = [(d, 100 + i, 1000) for i, d in enumerate(days) if i < 10 or i >= 28]
        data = {f"S{i}": gappy for i in range(3)}
        data["FULL"] = bars([100.0] * 30, dates=days)   # keeps the market calendar whole
        sectors = {f"S{i}": "X" for i in range(3)}
        row = ma.sector_rotation(data, sectors, {})[0]
        assert row["ret_5d"] is None

    def test_single_day_corporate_action_inside_the_window_is_excluded(self):
        days = calendar(30)
        clean = [100.0] * 30
        dividend = [100.0] * 25 + [83.3] * 5   # 20% stock dividend, -16.7% in a day
        data = {f"C{i}": bars(clean, dates=days) for i in range(3)}
        data["D"] = bars(dividend, dates=days)
        row = ma.sector_rotation(data, {k: "X" for k in data}, {})[0]
        assert row["count"] == 4
        assert row["ret_20d"] == 0.0

    def test_a_run_of_limit_downs_is_a_real_loss(self):
        days = calendar(30)
        falling = [100.0] * 25 + [100 * 0.9 ** j for j in range(1, 6)]
        data = {f"S{i}": bars(falling, dates=days) for i in range(3)}
        row = ma.sector_rotation(data, {k: "X" for k in data}, {})[0]
        assert row["ret_5d"] == pytest.approx(-40.95, abs=0.01)

    def test_stale_stock_is_not_counted(self):
        self.bars["OLD"] = bars([100] * 40, dates=self.days[:40])
        self.sectors["OLD"] = "半導體"
        assert ma.sector_rotation(self.bars, self.sectors, {})[0]["count"] == 3


def rising_universe(n_stocks, n_days, step=0.002):
    days = calendar(n_days)
    return days, {
        f"S{i}": bars([100 * (1 + step) ** j for j in range(n_days)], dates=days)
        for i in range(n_stocks)
    }


class TestBacktest:
    def test_empty_when_history_is_too_short(self):
        days, data = rising_universe(10, 50)
        assert ma.backtest(data, 20) == {
            "date": "", "horizon": 20, "periods": 0, "baseline": None, "setups": [],
        }

    def test_periods_do_not_overlap(self):
        days, data = rising_universe(10, 150)
        out = ma.backtest(data, 20)
        # signal indexes 128,108,88,68 are >= 59 with a forward bar; 48 lacks MA60
        assert out["periods"] == 4
        assert out["date"] == days[-1]

    def test_forward_return_is_exact(self):
        days, data = rising_universe(10, 100, step=0.01)
        out = ma.backtest(data, 20)
        expected = (1.01 ** 20 - 1) * 100
        assert out["baseline"]["avg_ret"] == pytest.approx(expected, abs=0.01)
        assert out["baseline"]["win_rate"] == 100.0

    def test_all_stocks_in_setup_means_zero_excess(self):
        days, data = rising_universe(10, 100, step=0.01)
        trend = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "trend_up")
        assert trend["avg_excess"] == pytest.approx(0.0, abs=0.01)
        assert trend["samples"] == trend["periods"] * 10

    def test_no_look_ahead_future_prices_never_change_membership(self):
        """Editing bars after the signal date must not change who qualifies."""
        days, data = rising_universe(10, 100, step=0.002)
        before = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "trend_up")["samples"]
        # Signal date is index 78; drop the close by a guard-safe amount on the last
        # day so returns change while membership stays identical.
        for sid in [f"S{i}" for i in range(5)]:
            rows = data[sid]
            data[sid] = rows[:-1] + [(rows[-1][0], rows[-1][1] * 0.92, rows[-1][2])]
        after = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "trend_up")["samples"]
        assert after == before

    def test_setup_under_five_members_does_not_count(self):
        days, data = rising_universe(10, 100)
        # no volume bursts anywhere → breakout has no members in any period
        breakout = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "breakout")
        assert breakout["periods"] == 0
        assert breakout["avg_ret"] is None and breakout["avg_excess"] is None

    def test_breakout_requires_volume_burst_up_day_and_ma60(self):
        days = calendar(100)
        closes = [100 * 1.002 ** j for j in range(100)]
        burst = [1000] * 100
        burst[78] = 5000
        data = {f"B{i}": bars(closes, volumes=burst, dates=days) for i in range(6)}
        data.update({f"Q{i}": bars(closes, dates=days) for i in range(6)})
        breakout = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "breakout")
        assert breakout["periods"] == 1
        assert breakout["samples"] == 6

    def test_pullback_needs_price_just_under_ma20_and_above_ma60(self):
        days = calendar(100)
        closes = [100 * 1.004 ** j for j in range(100)]
        closes[78] = closes[77] * 0.95   # 78 is the signal date for horizon 20
        data = {f"P{i}": bars(closes, dates=days) for i in range(6)}
        pullback = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "pullback")
        assert pullback["periods"] == 1

    def test_corporate_action_in_forward_window_is_excluded(self):
        days, data = rising_universe(10, 100)
        rows = data["S0"]
        data["S0"] = rows[:-1] + [(rows[-1][0], rows[-1][1] * 0.1, rows[-1][2])]
        baseline_samples = sum(
            s["samples"] for s in ma.backtest(data, 20)["setups"] if s["key"] == "trend_up"
        )
        assert baseline_samples % 10 != 0   # the split stock dropped from the last period
        assert ma.backtest(data, 20)["baseline"]["avg_ret"] > 0

    def test_beat_periods_counts_periods_above_baseline(self):
        days = calendar(100)
        strong = [100 * 1.01 ** j for j in range(100)]
        # flat, then falls: below its MAs at the signal, never in trend_up
        weak = [100.0] * 80 + [100 - j * 0.2 for j in range(20)]
        data = {f"U{i}": bars(strong, dates=days) for i in range(6)}
        data.update({f"W{i}": bars(weak, dates=days) for i in range(6)})
        trend = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "trend_up")
        assert trend["periods"] == 1      # signal day 78; 58 lacks MA60
        assert trend["beat_periods"] == 1
        assert trend["avg_excess"] > 0

    def test_entry_is_the_close_after_the_signal(self):
        """Signals publish overnight: the gap that fired the signal is not earned."""
        days = calendar(100)
        closes = [100.0] * 100
        # signal day 78 closes up 9% on a burst, then the price holds flat
        for i in range(78, 100):
            closes[i] = 109.0
        volumes = [1000] * 100
        volumes[78] = 5000
        data = {f"B{i}": bars(closes, volumes=volumes, dates=days) for i in range(6)}
        breakout = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "breakout")
        assert breakout["periods"] == 1
        assert breakout["avg_ret"] == 0.0     # flat after entry, not +9%

    def test_needs_a_bar_on_the_entry_day(self):
        days, data = rising_universe(10, 100)
        rows = data["S0"]
        data["S0"] = [r for r in rows if r[0] != days[79]]   # day after the signal
        trend = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "trend_up")
        assert trend["samples"] == 9

    def test_stock_dividend_while_held_is_excluded_at_every_horizon(self):
        for horizon in (5, 20, 60):
            days, data = rising_universe(10, 200)
            rows = data["S0"]
            cut = len(rows) - 1
            data["S0"] = rows[:cut] + [(rows[cut][0], rows[cut][1] * 0.833, rows[cut][2])]
            out = ma.backtest(data, horizon)
            trend = next(s for s in out["setups"] if s["key"] == "trend_up")
            assert trend["samples"] % 10 == 9, horizon   # only the last period loses S0

    def test_a_run_of_limit_downs_counts_against_the_setup(self):
        days = calendar(100)
        closes = [100 * 1.002 ** j for j in range(100)]
        for j in range(80, 85):
            closes[j] = closes[j - 1] * 0.9
        for j in range(85, 100):
            closes[j] = closes[84]
        data = {f"S{i}": bars(closes, dates=days) for i in range(10)}
        trend = next(s for s in ma.backtest(data, 20)["setups"] if s["key"] == "trend_up")
        assert trend["samples"] == 10
        assert trend["worst_period_ret"] == pytest.approx(-40.95, abs=0.5)

    def test_setups_keep_a_stable_order(self):
        _, data = rising_universe(10, 100)
        assert [s["key"] for s in ma.backtest(data, 20)["setups"]] == [
            "trend_up", "breakout", "near_high", "pullback",
        ]
