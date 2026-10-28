/**
 * signals.test.js — card signal + chip derivation (src/utils/signals.js)
 *
 * Missing fields (legacy score files, stocks without daily signals) must hide
 * the related UI rather than render a misleading fallback.
 */

import { describe, it, expect } from 'vitest'
import { resolveSignal, signalLabel, passRate, scoreChips, dailyChips } from '../src/utils/signals'

const rich = (overrides = {}) => ({
  score: 18, max_score: 24, eligible_count: 23, pass_rate: 78.3,
  signal: 'strong_buy', signal_label: '建議買進',
  risk_score: 0, risk_flags: [], fundamentals_uptrend: false,
  pe: { current: 22.1, median: 24.5, p25: 19.8 },
  ...overrides,
})

describe('resolveSignal', () => {
  it('returns the engine signal', () => {
    expect(resolveSignal(rich())).toBe('strong_buy')
    expect(resolveSignal(rich({ signal: 'buy' }))).toBe('buy')
    expect(resolveSignal(rich({ signal: 'watch' }))).toBe('watch')
    expect(resolveSignal(rich({ signal: 'neutral' }))).toBe('neutral')
  })

  it('maps 高風險避開 to avoid', () => {
    const s = rich({ signal: 'neutral', signal_label: '高風險避開', risk_score: 2 })
    expect(resolveSignal(s)).toBe('avoid')
  })

  it('treats risk_score >= 2 as avoid even if label is missing', () => {
    expect(resolveSignal(rich({ signal: 'neutral', signal_label: null, risk_score: 3 }))).toBe('avoid')
  })

  it('is null for legacy entries and missing scores', () => {
    expect(resolveSignal({ score: 18, max_score: 24 })).toBeNull()
    expect(resolveSignal(null)).toBeNull()
  })

  it('is null for unknown signal values', () => {
    expect(resolveSignal(rich({ signal: 'moon' }))).toBeNull()
  })
})

describe('signalLabel', () => {
  it('uses the engine label', () => {
    expect(signalLabel(rich())).toBe('建議買進')
  })

  it('is null without a signal', () => {
    expect(signalLabel({ score: 1, max_score: 24 })).toBeNull()
  })
})

describe('passRate', () => {
  it('returns pass_rate when present', () => {
    expect(passRate(rich())).toBe(78.3)
  })

  it('keeps a real zero', () => {
    expect(passRate(rich({ pass_rate: 0 }))).toBe(0)
  })

  it('is null for legacy entries (never derived from score/max_score)', () => {
    expect(passRate({ score: 18, max_score: 24 })).toBeNull()
  })
})

describe('scoreChips', () => {
  const keys = (s) => scoreChips(s).map(c => c.key)

  it('is empty for null / legacy entries without flags', () => {
    expect(scoreChips(null)).toEqual([])
    expect(scoreChips({ score: 18, max_score: 24 })).toEqual([])
  })

  it('adds uptrend chip when fundamentals_uptrend', () => {
    const chip = scoreChips(rich({ fundamentals_uptrend: true })).find(c => c.key === 'uptrend')
    expect(chip.icon).toBe('✅')
    expect(chip.text).toBe('轉強')
  })

  it('adds strong value chip when P/E below 5y p25', () => {
    const chip = scoreChips(rich({ pe: { current: 15, median: 24.5, p25: 19.8 } })).find(c => c.key === 'value')
    expect(chip.text).toBe('低估')
    expect(chip.tone).toBe('good')
  })

  it('adds soft value chip when P/E only below median', () => {
    const chip = scoreChips(rich()).find(c => c.key === 'value')
    expect(chip.text).toBe('偏低')
    expect(chip.tone).toBe('soft')
  })

  it('no value chip when P/E above median or missing', () => {
    expect(keys(rich({ pe: { current: 30, median: 24.5, p25: 19.8 } }))).not.toContain('value')
    expect(keys(rich({ pe: { current: null, median: null, p25: null } }))).not.toContain('value')
    expect(keys(rich({ pe: undefined }))).not.toContain('value')
  })

  it('adds risk chip with count and flag names only when risk_score > 0', () => {
    const s = rich({
      risk_score: 2,
      risk_flags: [{ category: '獲利排雷', name: '自由現金流轉負' }, { category: '存貨排雷', name: '存貨飆升去化慢' }],
    })
    const chip = scoreChips(s).find(c => c.key === 'risk')
    expect(chip.text).toBe('2')
    expect(chip.keepText).toBe(true)
    expect(chip.title).toContain('自由現金流轉負')
    expect(chip.title).toContain('存貨飆升去化慢')
    expect(keys(rich({ risk_score: 0 }))).not.toContain('risk')
  })
})

describe('dailyChips', () => {
  const sig = (o = {}) => ({
    close: 1045, avg_volume_5d: 1000, vol_ratio: 1.1,
    ma20: 1010, ma60: 980, above_ma20: true, above_ma60: true,
    high_52w: 1100, pct_from_52w_high: -5, inst_net_5d: 12500, inst_streak: 3,
    foreign_net_1d: 3200, trust_net_1d: 400, ...o,
  })
  const find = (chips, key) => chips.find(c => c.key === key)

  it('is empty without daily signals', () => {
    expect(dailyChips(null, {}, false)).toEqual([])
  })

  it('institutional streak chip: +N buy (up tone), -N sell (down tone)', () => {
    const buy = find(dailyChips(sig(), {}, false), 'inst')
    expect(buy.text).toBe('+3')
    expect(buy.tone).toBe('up')
    expect(buy.keepText).toBe(true)
    expect(buy.title).toContain('12,500')
    const sell = find(dailyChips(sig({ inst_streak: -4 }), {}, false), 'inst')
    expect(sell.text).toBe('-4')
    expect(sell.tone).toBe('down')
  })

  it('no institutional chip for streaks shorter than 2 days or null', () => {
    expect(find(dailyChips(sig({ inst_streak: 1 }), {}, false), 'inst')).toBeUndefined()
    expect(find(dailyChips(sig({ inst_streak: null }), {}, false), 'inst')).toBeUndefined()
  })

  it('moving-average chip: 月季線上 above both, 月線上 above MA20 only, none below', () => {
    expect(find(dailyChips(sig(), {}, false), 'ma').text).toBe('月季線上')
    expect(find(dailyChips(sig({ above_ma60: false }), {}, false), 'ma').text).toBe('月線上')
    expect(find(dailyChips(sig({ above_ma60: null }), {}, false), 'ma').text).toBe('月線上')
    expect(find(dailyChips(sig({ above_ma20: false }), {}, false), 'ma')).toBeUndefined()
  })

  it('volume chip from nightly ratio after close, only when >= 1.5', () => {
    expect(find(dailyChips(sig({ vol_ratio: 2.14 }), {}, false), 'vol').text).toBe('×2.1')
    expect(find(dailyChips(sig({ vol_ratio: 1.2 }), {}, false), 'vol')).toBeUndefined()
  })

  it('volume chip uses live volume ÷ 5-day average while market is open', () => {
    const chip = find(dailyChips(sig({ vol_ratio: 0.5, avg_volume_5d: 1000 }), { volume: 3000 }, true), 'vol')
    expect(chip.text).toBe('×3.0')
    expect(chip.title).toContain('盤中')
  })

  it('near-52w-high chip within 5%, 創高 at the high', () => {
    expect(find(dailyChips(sig({ pct_from_52w_high: -3.2 }), {}, false), 'high').text).toBe('距高-3.2%')
    expect(find(dailyChips(sig({ pct_from_52w_high: 0 }), {}, false), 'high').text).toBe('創高')
    expect(find(dailyChips(sig({ pct_from_52w_high: -12 }), {}, false), 'high')).toBeUndefined()
    expect(find(dailyChips(sig({ pct_from_52w_high: null }), {}, false), 'high')).toBeUndefined()
  })
})
