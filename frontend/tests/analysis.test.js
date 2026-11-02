/**
 * analysis.test.js — the rules that decide what is called a candidate.
 *
 * The contract that matters: missing data stays missing (it can never lift a
 * stock onto the list), and risk always outranks a good-looking score.
 */

import { describe, it, expect } from 'vitest'
import {
  WEIGHTS, assessStock, shortlist, marketSummary, marketRead, sectorSnapshot, watchAlerts,
  rebasedComparison,
} from '../src/utils/analysis'

const stock = (over = {}) => ({
  stock_id: '2330', name: '台積電', sector: '半導體', close_price: 100, price_change_pct: 1, ...over,
})
const score = (over = {}) => ({
  score: 18, max_score: 24, eligible_count: 23, pass_rate: 80, risk_score: 0,
  signal: 'strong_buy', signal_label: '建議買進', fundamentals_uptrend: false,
  pe: { current: 20, median: 25, p25: 18 }, ...over,
})
const daily = (over = {}) => ({
  ma20: 95, ma60: 90, above_ma20: true, above_ma60: true, pct_from_52w_high: -4,
  inst_streak: 3, inst_net_5d: 500, close: 100, ...over,
})
const dim = (a, key) => a.dimensions.find(d => d.key === key).score

describe('dimensions', () => {
  it('weights sum to 1', () => {
    expect(Object.values(WEIGHTS).reduce((a, b) => a + b, 0)).toBeCloseTo(1)
  })

  it('quality is the pass rate, +5 for a fundamentals uptrend, capped at 100', () => {
    expect(dim(assessStock({ stock: stock(), score: score(), daily: daily() }), 'quality')).toBe(80)
    expect(dim(assessStock({ stock: stock(), score: score({ fundamentals_uptrend: true }) }), 'quality')).toBe(85)
    expect(dim(assessStock({ stock: stock(), score: score({ pass_rate: 98, fundamentals_uptrend: true }) }), 'quality')).toBe(100)
  })

  it('quality is unknown when too few criteria were scored', () => {
    // 6/6 on a new listing or after failed datasets is not a perfect score
    const thin = score({ pass_rate: 100, score: 6, eligible_count: 6 })
    const a = assessStock({ stock: stock(), score: thin, daily: daily() })
    expect(dim(a, 'quality')).toBe(null)
    expect(a.composite).toBe(null)
    expect(a.stance.key).toBe('insufficient')
    expect(a.cautions.join('｜')).toContain('6 項')
  })

  it('twelve scored criteria are enough', () => {
    const a = assessStock({ stock: stock(), score: score({ eligible_count: 12 }) })
    expect(dim(a, 'quality')).toBe(80)
  })

  it('an unknown criteria count is not trusted', () => {
    const a = assessStock({ stock: stock(), score: score({ eligible_count: undefined }) })
    expect(dim(a, 'quality')).toBe(null)
  })

  it('trend earns MA20 35 + MA60 35 + nearness to the high 30', () => {
    expect(dim(assessStock({ stock: stock(), daily: daily() }), 'trend')).toBe(100)
    expect(dim(assessStock({ stock: stock(), daily: daily({ above_ma20: false }) }), 'trend')).toBe(65)
    expect(dim(assessStock({ stock: stock(), daily: daily({ pct_from_52w_high: -10 }) }), 'trend')).toBe(90)
    expect(dim(assessStock({ stock: stock(), daily: daily({ pct_from_52w_high: -25 }) }), 'trend')).toBe(80)
    expect(dim(assessStock({ stock: stock(), daily: daily({ pct_from_52w_high: -40 }) }), 'trend')).toBe(70)
  })

  it('trend rescales when a component is missing rather than scoring it as zero', () => {
    expect(dim(assessStock({ stock: stock(), daily: daily({ pct_from_52w_high: null }) }), 'trend')).toBe(100)
    expect(dim(assessStock({ stock: stock(), daily: daily({ above_ma60: null, pct_from_52w_high: null }) }), 'trend')).toBe(100)
  })

  it('trend needs at least one MA flag', () => {
    const a = assessStock({ stock: stock(), daily: daily({ above_ma20: null, above_ma60: null }) })
    expect(dim(a, 'trend')).toBe(null)
  })

  it('flow centres on 50, moves 8 per streak day, clamped at ±5 days', () => {
    expect(dim(assessStock({ stock: stock(), daily: daily({ inst_streak: 0, inst_net_5d: null }) }), 'flow')).toBe(50)
    expect(dim(assessStock({ stock: stock(), daily: daily({ inst_streak: 3, inst_net_5d: null }) }), 'flow')).toBe(74)
    expect(dim(assessStock({ stock: stock(), daily: daily({ inst_streak: 9, inst_net_5d: 1 }) }), 'flow')).toBe(100)
    expect(dim(assessStock({ stock: stock(), daily: daily({ inst_streak: -9, inst_net_5d: -1 }) }), 'flow')).toBe(0)
    expect(dim(assessStock({ stock: stock(), daily: daily({ inst_streak: null }) }), 'flow')).toBe(null)
  })

  it('value compares P/E with its own five-year range', () => {
    const v = (pe) => dim(assessStock({ stock: stock(), score: score({ pe }) }), 'value')
    expect(v({ current: 17, median: 25, p25: 18 })).toBe(90)
    expect(v({ current: 20, median: 25, p25: 18 })).toBe(65)
    expect(v({ current: 30, median: 25, p25: 18 })).toBe(40)
    expect(v({ current: 40, median: 25, p25: 18 })).toBe(20)
  })

  it('value is unknown for losses and missing history', () => {
    const v = (pe) => dim(assessStock({ stock: stock(), score: score({ pe }) }), 'value')
    expect(v({ current: -5, median: 25, p25: 18 })).toBe(null)
    expect(v({ current: 20, median: null, p25: null })).toBe(null)
    expect(v(undefined)).toBe(null)
  })
})

describe('composite', () => {
  it('is the weighted mean of available dimensions', () => {
    const a = assessStock({ stock: stock(), score: score(), daily: daily({ inst_streak: 0, inst_net_5d: null }) })
    // 80×.4 + 100×.25 + 50×.2 + 65×.15 = 76.75
    expect(a.composite).toBe(77)
  })

  it('re-normalises the weights when one dimension is missing', () => {
    const a = assessStock({ stock: stock(), score: score({ pe: null }), daily: daily({ inst_streak: 0, inst_net_5d: null }) })
    // (32 + 25 + 10) / .85 = 78.8
    expect(a.composite).toBe(79)
  })

  it('is null without the fundamental score, however good the chart looks', () => {
    expect(assessStock({ stock: stock(), score: null, daily: daily() }).composite).toBe(null)
    expect(assessStock({ stock: stock(), score: score({ pass_rate: null }), daily: daily() }).composite).toBe(null)
  })

  it('is null with fewer than three dimensions', () => {
    expect(assessStock({ stock: stock(), score: score({ pe: null }), daily: null }).composite).toBe(null)
  })

  it('never invents a score from nothing', () => {
    const a = assessStock({ stock: stock() })
    expect(a.composite).toBe(null)
    expect(a.stance.key).toBe('insufficient')
    expect(a.dimensions.every(d => d.score === null)).toBe(true)
  })

  it('subtracts 10 per risk item and floors at 0', () => {
    const clean = assessStock({ stock: stock(), score: score(), daily: daily() }).composite
    expect(assessStock({ stock: stock(), score: score({ risk_score: 1 }), daily: daily() }).composite).toBe(clean - 10)
    const low = score({ pass_rate: 1, risk_score: 9, pe: { current: 99, median: 10, p25: 8 } })
    expect(assessStock({ stock: stock(), score: low, daily: daily({ above_ma20: false, above_ma60: false, inst_streak: -9, inst_net_5d: -1 }) }).composite).toBe(0)
  })
})

describe('stance', () => {
  const stance = (s, d, st = stock()) => assessStock({ stock: st, score: s, daily: d }).stance.key

  it('risk outranks everything', () => {
    expect(stance(score({ risk_score: 2, pass_rate: 99 }), daily())).toBe('avoid')
    expect(stance(score({ signal_label: '高風險避開', signal: 'neutral', risk_score: 1 }), daily())).toBe('avoid')
  })

  it('avoid applies even when other data is missing', () => {
    expect(stance(score({ risk_score: 3 }), null)).toBe('avoid')
  })

  it('a strong stock stretched above its monthly line waits for a pullback', () => {
    expect(stance(score(), daily({ ma20: 85 }))).toBe('wait_pullback')
  })

  it('exactly 10% above MA20 is not yet stretched', () => {
    expect(stance(score(), daily({ ma20: 100 / 1.1 }))).toBe('candidate')
  })

  it('candidate needs a high composite and the live price above MA20', () => {
    expect(stance(score(), daily())).toBe('candidate')
    expect(stance(score(), daily({ ma20: 105 }))).not.toBe('candidate')
  })

  it('uses the live price, not last night\'s close', () => {
    expect(stance(score(), daily({ ma20: 95 }), stock({ close_price: 90 }))).toBe('watch')
  })

  it('middling composites are watch, weak ones pass', () => {
    const weak = daily({ above_ma20: false, above_ma60: false, pct_from_52w_high: -40, inst_streak: -3, inst_net_5d: -1 })
    expect(stance(score({ pass_rate: 70 }), daily({ inst_streak: 0, inst_net_5d: null, ma20: 105 }))).toBe('watch')
    expect(stance(score({ pass_rate: 30, pe: { current: 40, median: 25, p25: 18 } }), weak)).toBe('pass')
  })
})

describe('reasons', () => {
  it('states strengths with their numbers', () => {
    const a = assessStock({
      stock: stock(), score: score({ fundamentals_uptrend: true }),
      daily: daily({ inst_streak: 5, inst_net_5d: 12500 }),
    })
    const text = a.strengths.join('｜')
    expect(text).toContain('18/23')
    expect(text).toContain('連買 5 日')
    expect(text).toContain('12,500')
    expect(text).toContain('月線與季線')
    expect(text).toContain('P/E 20')
  })

  it('states cautions: risk first, then trend, flow and valuation', () => {
    const a = assessStock({
      stock: stock({ close_price: 80 }),
      score: score({ pass_rate: 40, risk_score: 1, risk_flags: [{ category: 'x', name: '自由現金流轉負' }], pe: { current: 40, median: 25, p25: 18 } }),
      daily: daily({ inst_streak: -4, above_ma20: false, above_ma60: false, pct_from_52w_high: -30 }),
    })
    expect(a.cautions[0]).toContain('自由現金流轉負')
    const text = a.cautions.join('｜')
    expect(text).toContain('40')
    expect(text).toContain('跌破月線')
    expect(text).toContain('跌破季線')
    expect(text).toContain('連賣 4 日')
    expect(text).toContain('中位數 25')
    expect(text).toContain('-30')
  })

  it('warns when the price is stretched above MA20', () => {
    const a = assessStock({ stock: stock(), score: score(), daily: daily({ ma20: 85 }) })
    expect(a.cautions.join('｜')).toContain('高於月線')
  })

  it('stays silent about what it does not know', () => {
    const a = assessStock({ stock: stock() })
    expect(a.strengths).toEqual([])
    expect(a.cautions).toEqual([])
  })
})

describe('shortlist', () => {
  const pool = [
    stock({ stock_id: 'A' }), stock({ stock_id: 'B' }), stock({ stock_id: 'C' }),
    stock({ stock_id: 'D' }), stock({ stock_id: 'E' }),
  ]
  const scores = {
    A: score({ pass_rate: 70 }),
    B: score({ pass_rate: 90 }),
    C: score({ pass_rate: 95, risk_score: 2 }),
    D: score({ pass_rate: 90 }),
  }
  const signals = {
    A: daily(), B: daily({ inst_net_5d: 100 }), C: daily(), D: daily({ inst_net_5d: 900 }), E: daily(),
  }

  it('ranks by composite then institutional net, and excludes risk and thin data', () => {
    expect(shortlist(pool, { scores, signals }).map(r => r.stock.stock_id)).toEqual(['D', 'B', 'A'])
  })

  it('honours the limit', () => {
    expect(shortlist(pool, { scores, signals }, 1)).toHaveLength(1)
  })

  it('is empty before scores load', () => {
    expect(shortlist(pool, { scores: {}, signals })).toEqual([])
  })

  it('keeps wait_pullback names on the list, labelled as such', () => {
    const out = shortlist([stock({ stock_id: 'A' })], { scores: { A: score() }, signals: { A: daily({ ma20: 85 }) } })
    expect(out[0].assessment.stance.key).toBe('wait_pullback')
  })
})

describe('marketSummary', () => {
  const pool = [
    stock({ stock_id: 'A', price_change_pct: 2 }),
    stock({ stock_id: 'B', price_change_pct: -1 }),
    stock({ stock_id: 'C', price_change_pct: 0 }),
    stock({ stock_id: 'D', price_change_pct: null }),
  ]

  it('counts breadth and ignores missing changes', () => {
    const m = marketSummary(pool, { scores: {}, signals: {} })
    expect(m).toMatchObject({ total: 4, advancers: 1, decliners: 1, unchanged: 1, medianChange: 0 })
  })

  it('reports MA breadth only with a meaningful sample', () => {
    expect(marketSummary(pool, { scores: {}, signals: { A: daily() } }).pctAboveMa20).toBe(null)
    const many = Array.from({ length: 20 }, (_, i) => stock({ stock_id: `S${i}` }))
    const signals = Object.fromEntries(many.map((s, i) => [s.stock_id, daily({ above_ma20: i % 4 !== 0 })]))
    expect(marketSummary(many, { scores: {}, signals }).pctAboveMa20).toBe(75)
  })

  it('tallies signals through resolveSignal so avoid is its own bucket', () => {
    const scores = {
      A: score(), B: score({ signal: 'watch', signal_label: '觀察清單' }),
      C: score({ signal: 'neutral', signal_label: '高風險避開', risk_score: 2 }),
    }
    const m = marketSummary(pool, { scores, signals: {} })
    expect(m.signalCounts).toMatchObject({ strong_buy: 1, watch: 1, avoid: 1, buy: 0 })
    expect(m.scored).toBe(3)
  })

  it('counts institutional streaks of three days or more', () => {
    const signals = { A: daily({ inst_streak: 3 }), B: daily({ inst_streak: 2 }), C: daily({ inst_streak: -3 }) }
    expect(marketSummary(pool, { scores: {}, signals })).toMatchObject({ instBuying: 1, instSelling: 1 })
  })

  it('reports institutional counts as unknown without flow data, not zero', () => {
    expect(marketSummary(pool, { scores: {}, signals: {} })).toMatchObject({ instBuying: null, instSelling: null })
    expect(marketSummary(pool, { scores: {}, signals: { A: daily({ inst_streak: 1 }) } }))
      .toMatchObject({ instBuying: 0, instSelling: 0 })
  })

  it('handles an empty pool', () => {
    expect(marketSummary([], { scores: {}, signals: {} })).toMatchObject({ total: 0, medianChange: null })
  })
})

describe('marketRead', () => {
  it('reads the share of stocks above MA20', () => {
    expect(marketRead({ pctAboveMa20: 80 }).key).toBe('hot')
    expect(marketRead({ pctAboveMa20: 60 }).key).toBe('positive')
    expect(marketRead({ pctAboveMa20: 40 }).key).toBe('mixed')
    expect(marketRead({ pctAboveMa20: 20 }).key).toBe('weak')
  })

  it('describes the market rather than instructing the reader', () => {
    for (const pct of [80, 60, 40, 20]) {
      expect(marketRead({ pctAboveMa20: pct }).text).not.toMatch(/宜|應|不急|優先|建議/)
    }
  })

  it('declines to read without data', () => {
    expect(marketRead({ pctAboveMa20: null })).toBe(null)
  })
})

describe('sectorSnapshot', () => {
  const pool = [
    stock({ stock_id: 'A', sector: '半導體', price_change_pct: 2 }),
    stock({ stock_id: 'B', sector: '半導體', price_change_pct: 4 }),
    stock({ stock_id: 'C', sector: '半導體', price_change_pct: -1 }),
    stock({ stock_id: 'D', sector: '其他', price_change_pct: 9 }),
    stock({ stock_id: 'E', sector: '金融', price_change_pct: 1 }),
  ]

  it('aggregates live change, pass rate and leaders; drops 其他 and thin sectors', () => {
    const scores = { A: score({ pass_rate: 80 }), B: score({ pass_rate: 60 }) }
    const out = sectorSnapshot(pool, { scores })
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ name: '半導體', count: 3, medianChange: 2, avgPassRate: 70 })
    expect(out[0].upShare).toBeCloseTo(66.7, 1)
    expect(out[0].leader.stock_id).toBe('B')
  })

  it('avgPassRate is null when nothing is scored', () => {
    expect(sectorSnapshot(pool, { scores: {} })[0].avgPassRate).toBe(null)
  })
})

describe('rebasedComparison', () => {
  const bars = (rows) => rows.map(([date, close]) => ({ date, close }))

  it('rebases every stock to 100 on the first shared date', () => {
    const out = rebasedComparison([
      { id: 'A', bars: bars([['d1', 50], ['d2', 55]]) },
      { id: 'B', bars: bars([['d1', 200], ['d2', 180]]) },
    ])
    expect(out.dates).toEqual(['d1', 'd2'])
    expect(out.series).toEqual([{ id: 'A', values: [100, 110] }, { id: 'B', values: [100, 90] }])
  })

  it('uses only dates every stock traded', () => {
    const out = rebasedComparison([
      { id: 'A', bars: bars([['d1', 10], ['d2', 11], ['d3', 12]]) },
      { id: 'NEW', bars: bars([['d2', 20], ['d3', 22]]) },
    ])
    expect(out.dates).toEqual(['d2', 'd3'])
    expect(out.series[0].values[0]).toBe(100)
  })

  it('is empty when nothing overlaps or nothing is selected', () => {
    expect(rebasedComparison([]).dates).toEqual([])
    expect(rebasedComparison([
      { id: 'A', bars: bars([['d1', 10]]) }, { id: 'B', bars: bars([['d2', 10]]) },
    ]).dates).toEqual([])
  })

  it('ignores unusable closes', () => {
    const out = rebasedComparison([{ id: 'A', bars: bars([['d1', 0], ['d2', null], ['d3', 10]]) }])
    expect(out.dates).toEqual(['d3'])
  })
})

describe('watchAlerts', () => {
  const keys = (a) => watchAlerts(a).map(x => x.key)

  it('is quiet for a healthy holding', () => {
    expect(keys({ stock: stock(), score: score(), daily: daily() })).toEqual([])
  })

  it('flags a live break of the monthly and quarterly lines', () => {
    expect(keys({ stock: stock({ close_price: 92 }), score: score(), daily: daily() })).toEqual(['below_ma20'])
    expect(keys({ stock: stock({ close_price: 85 }), score: score(), daily: daily() })).toEqual(['below_ma60'])
  })

  it('flags institutional selling, risk items and deep drawdowns', () => {
    expect(keys({ stock: stock(), score: score({ risk_score: 1, risk_flags: [] }), daily: daily({ inst_streak: -3, pct_from_52w_high: -20 }) }))
      .toEqual(['risk', 'inst_selling', 'drawdown'])
  })

  it('needs data to alert', () => {
    expect(keys({ stock: stock({ close_price: null }), score: null, daily: null })).toEqual([])
  })
})
