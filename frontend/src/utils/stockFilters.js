/**
 * stockFilters.js — 篩選器組合 over the fixed 600-stock payload (frontend-only;
 * the stock API query never changes — CLAUDE.md rules 3/4).
 *
 * Conditions are AND-combined. A stock whose required field is missing / null
 * (legacy score file, no nightly signals yet) never matches — missing data must
 * not sneak a stock into a "worth buying" list.
 */

import { volumeRatio } from './signals'

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : NaN)

/** ctx: {score, daily, stock, marketOpen} for one stock */
export const CONDITIONS = {
  pass75:    { label: '通過率≥75%',    test: (c) => num(c.score?.pass_rate) >= 75 },
  pass60:    { label: '通過率≥60%',    test: (c) => num(c.score?.pass_rate) >= 60 },
  noRisk:    { label: '無排雷',         test: (c) => c.score?.risk_score === 0 },
  uptrend:   { label: '營收EPS轉強✅',  test: (c) => c.score?.fundamentals_uptrend === true },
  cheap:     { label: 'P/E<5年p25',    test: (c) => num(c.score?.pe?.current) < num(c.score?.pe?.p25) },
  aboveMa20: { label: '站上月線',       test: (c) => c.daily?.above_ma20 === true },
  aboveMa60: { label: '站上季線',       test: (c) => c.daily?.above_ma60 === true },
  instBuy3:  { label: '法人連買≥3日',   test: (c) => num(c.daily?.inst_streak) >= 3 },
  volBurst:  { label: '量比≥2',         test: (c) => num(volumeRatio(c.daily, c.stock, c.marketOpen).ratio) >= 2 },
  priceUp:   { label: '今日上漲',       test: (c) => num(c.stock?.price_change_pct) > 0 },
}

export const PRESETS = [
  { key: 'quality',  label: '穩健優質', conditions: ['pass75', 'noRisk'] },
  { key: 'turning',  label: '轉強起漲', conditions: ['uptrend', 'aboveMa20', 'instBuy3'] },
  { key: 'value',    label: '低估待買', conditions: ['cheap', 'pass60', 'noRisk'] },
  { key: 'breakout', label: '量增突破', conditions: ['volBurst', 'priceUp', 'aboveMa60'] },
]

/** Preset key whose conditions equal `active` exactly (order-insensitive), else null. */
export function presetFor(active) {
  const want = [...active].sort().join('|')
  return PRESETS.find(p => [...p.conditions].sort().join('|') === want)?.key ?? null
}

/**
 * @param stocks  flat stock list (each with stock_id + quote fields)
 * @param active  condition keys
 * @param {{scores: object, signals: object, marketOpen: boolean}} data
 */
export function applyFilters(stocks, active, { scores, signals, marketOpen }) {
  const tests = active.map(k => CONDITIONS[k]?.test).filter(Boolean)
  if (!tests.length) return stocks
  return stocks.filter((stock) => {
    const c = { stock, score: scores?.[stock.stock_id], daily: signals?.[stock.stock_id], marketOpen }
    return tests.every(t => t(c))
  })
}

/** pass_rate desc → inst_net_5d desc, nulls last. Returns a new array. */
export function sortByPotential(stocks, { scores, signals }) {
  const key = (v) => (Number.isFinite(v) ? v : -Infinity)
  return stocks.slice().sort((a, b) => {
    const pr = key(scores?.[b.stock_id]?.pass_rate) - key(scores?.[a.stock_id]?.pass_rate)
    if (pr !== 0 && !Number.isNaN(pr)) return pr
    const inst = key(signals?.[b.stock_id]?.inst_net_5d) - key(signals?.[a.stock_id]?.inst_net_5d)
    return Number.isNaN(inst) ? 0 : inst
  })
}
