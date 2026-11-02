/**
 * fakeApi.js — an in-memory backend that follows the SPEC.md contracts, so
 * integration tests exercise the real stores, composables and components, with
 * only the network replaced. Every call is recorded for assertions.
 */

import { vi } from 'vitest'

export const STOCKS = [
  { stock_id: '2330', name: '台積電', rank: 1, volume: 45_000_000, turnover_rate: 0.82, price_change_pct: 2.35, color_tier: 'light_red', close_price: 100 },
  { stock_id: '2454', name: '聯發科', rank: 2, volume: 20_000_000, turnover_rate: 3.1, price_change_pct: -1.2, color_tier: 'light_green', close_price: 100 },
  { stock_id: '2303', name: '聯電', rank: 3, volume: 15_000_000, turnover_rate: 1.2, price_change_pct: 0.5, color_tier: 'neutral', close_price: 100 },
]

const SCORE = {
  score: 19, max_score: 24, eligible_count: 23, pass_rate: 82.6, fundamentals_uptrend: true,
  signal: 'strong_buy', signal_label: '建議買進', risk_score: 0, risk_flags: [],
  pe: { current: 20, median: 25, p25: 18 },
}

const SIGNAL = {
  close: 100, avg_volume_5d: 40_000_000, vol_ratio: 1.1, ma20: 95, ma60: 90, high_52w: 104,
  pct_from_52w_high: -3.8, inst_net_5d: 12500, inst_streak: 4, foreign_net_1d: 3200,
  trust_net_1d: 400, above_ma20: true, above_ma60: true,
}

const days = (n) => Array.from({ length: n }, (_, i) => {
  const d = new Date(Date.UTC(2026, 5, 1 + i))
  return d.toISOString().slice(0, 10)
})

function historyBody(stockId) {
  const dates = days(70)
  return {
    stock_id: stockId,
    date: dates[dates.length - 1],
    bars: dates.map((date, i) => ({
      date, close: 90 + i * 0.2, volume: 40_000_000 + i * 1000,
      ma20: i >= 19 ? 88 + i * 0.2 : null, ma60: i >= 59 ? 85 + i * 0.2 : null,
    })),
    flows: dates.slice(-20).map((date, i) => ({
      date, foreign_net: i % 3 ? 500 : -200, trust_net: 50, dealer_net: 0,
    })),
  }
}

const TREND = {
  date: '2026-08-09',
  universe: 3,
  breadth: days(30).map((date, i) => ({
    date, advancers: 300, decliners: 200, unchanged: 20,
    pct_above_ma20: 50 + i * 0.5, pct_above_ma60: 45 + i * 0.3, ew_index: 100 + i * 0.1,
  })),
  sectors: [{ name: '半導體', count: 3, ret_5d: 1.2, ret_20d: 4.5, ret_60d: 9.1, pct_above_ma20: 66.7, inst_net_5d: 9000 }],
}

const BACKTEST = (horizon) => ({
  date: '2026-08-09',
  horizon,
  periods: 11,
  baseline: { avg_ret: 1.8, win_rate: 54.2 },
  setups: [
    { key: 'trend_up', label: '站上月季線', periods: 11, beat_periods: 7, samples: 2400, avg_ret: 2.6, avg_excess: 0.8, win_rate: 57.1, worst_period_ret: -9.4 },
    { key: 'breakout', label: '量增突破', periods: 0, beat_periods: 0, samples: 0, avg_ret: null, avg_excess: null, win_rate: null, worst_period_ret: null },
  ],
})

function json(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })
}

export function fakeApi(overrides = {}) {
  const state = {
    watchlist: overrides.watchlist ?? [],
    stocks: overrides.stocks ?? STOCKS,
    sectors: overrides.sectors ?? null,
    scores: overrides.scores ?? { 2330: SCORE, 2454: { ...SCORE, pass_rate: 40, signal: 'neutral', signal_label: '不建議買進' } },
    signals: overrides.signals ?? { 2330: SIGNAL, 2454: { ...SIGNAL, above_ma20: false } },
    trend: overrides.trend ?? TREND,
    backtest: overrides.backtest ?? BACKTEST,
    failing: overrides.failing ?? [],
  }

  const calls = []

  const handler = (url, init = {}) => {
    const path = String(url)
    calls.push({ path, method: init.method ?? 'GET' })
    if (state.failing.some(prefix => path.startsWith(prefix))) return json({ detail: 'boom' }, 500)

    if (path.startsWith('/api/stocks/top100')) {
      return json({
        mode: 'volume', date: '2026-08-09', market_open: false, updated_at: '2026-08-09T14:00:00+08:00',
        sectors: state.sectors ?? (state.stocks.length ? [{ name: '半導體', stocks: state.stocks }] : []),
      })
    }
    const history = path.match(/^\/api\/stocks\/([^/]+)\/history/)
    if (history) return json(historyBody(history[1]))
    const scoreHistory = path.match(/^\/api\/scores\/([^/]+)\/history/)
    if (scoreHistory) {
      return json({
        stock_id: scoreHistory[1],
        points: [
          { date: '2026-08-07', score: 18, eligible_count: 23, pass_rate: 78.3, signal: 'strong_buy', risk_score: 0 },
          { date: '2026-08-08', score: 19, eligible_count: 23, pass_rate: 82.6, signal: 'strong_buy', risk_score: 0 },
        ],
      })
    }
    const detail = path.match(/^\/api\/scores\/([^/?]+)$/)
    if (detail) {
      return json({
        date: '2026-08-09', stock_id: detail[1],
        criteria: [{ id: 'roe', label: 'ROE (TTM) > 12%', pass: true, value_label: '28.1%' }],
        risk_criteria: [],
      })
    }
    if (path.startsWith('/api/scores')) {
      return json({ date: '2026-08-09', generated_at: '2026-08-09T03:40:00+08:00', scores: state.scores, fetching: false })
    }
    if (path.startsWith('/api/signals')) {
      return json({ date: '2026-08-08', generated_at: 'g1', signals: state.signals })
    }
    if (path.startsWith('/api/market/trend')) return json(state.trend)
    if (path.startsWith('/api/market/backtest')) {
      const horizon = Number(new URL(path, 'http://x').searchParams.get('horizon'))
      return json(state.backtest(horizon))
    }
    if (path.startsWith('/api/etf')) {
      return json({ sort_by: 'turnover', date: '2026-08-09', market_open: false, updated_at: 'x', etfs: [] })
    }
    const pin = path.match(/^\/api\/watchlist\/([^/]+)$/)
    if (pin && init.method === 'PUT') {
      const quote = state.stocks.find(s => s.stock_id === pin[1])
      const item = { stock_id: pin[1], note: '', added_at: 't', quote: { ...quote, sector: '半導體' } }
      state.watchlist.push(item)
      return json(item)
    }
    if (pin && init.method === 'DELETE') {
      state.watchlist = state.watchlist.filter(i => i.stock_id !== pin[1])
      return Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve(null) })
    }
    if (path.startsWith('/api/watchlist')) return json({ items: state.watchlist })
    return json({ detail: `unhandled ${path}` }, 404)
  }

  const fetchMock = vi.fn(handler)
  vi.stubGlobal('fetch', fetchMock)
  return { calls, state, fetchMock }
}

export const emptyTrend = { date: '', universe: 0, breadth: [], sectors: [] }
export const emptyBacktest = (horizon) => ({ date: '', horizon, periods: 0, baseline: null, setups: [] })
