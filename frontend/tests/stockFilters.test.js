/**
 * stockFilters.test.js — 篩選器組合 (src/utils/stockFilters.js) + filterStore
 *
 * AND-combined atomic conditions over the same 600-stock payload; a stock whose
 * needed field is null never matches. Results sort by pass_rate desc, then
 * inst_net_5d desc.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { CONDITIONS, PRESETS, applyFilters, sortByPotential, presetFor } from '../src/utils/stockFilters'
import { useFilterStore } from '../src/stores/filterStore'

const stock = (id, o = {}) => ({ stock_id: id, name: id, price_change_pct: 1, volume: 1000, ...o })

const ctx = (scores = {}, signals = {}, marketOpen = false) => ({ scores, signals, marketOpen })

const ids = (list) => list.map(s => s.stock_id)

describe('PRESETS', () => {
  it('match the confirmed spec', () => {
    const byKey = Object.fromEntries(PRESETS.map(p => [p.key, p.conditions]))
    expect(byKey.quality).toEqual(['pass75', 'noRisk'])
    expect(byKey.turning).toEqual(['uptrend', 'aboveMa20', 'instBuy3'])
    expect(byKey.value).toEqual(['cheap', 'pass60', 'noRisk'])
    expect(byKey.breakout).toEqual(['volBurst', 'priceUp', 'aboveMa60'])
  })

  it('every preset condition exists', () => {
    for (const p of PRESETS) for (const c of p.conditions) expect(CONDITIONS[c]).toBeDefined()
  })

  it('presetFor recognises an exact preset selection regardless of order', () => {
    expect(presetFor(['noRisk', 'pass75'])).toBe('quality')
    expect(presetFor(['noRisk'])).toBeNull()
  })
})

describe('applyFilters', () => {
  const stocks = [stock('A'), stock('B'), stock('C', { price_change_pct: -2 })]
  const scores = {
    A: { pass_rate: 80, risk_score: 0, fundamentals_uptrend: true, pe: { current: 10, median: 15, p25: 12 } },
    B: { pass_rate: 70, risk_score: 1 },
    C: { pass_rate: 90, risk_score: 0 },
  }
  const signals = {
    A: { above_ma20: true, above_ma60: true, inst_streak: 4, vol_ratio: 2.5, avg_volume_5d: 400 },
    B: { above_ma20: true, above_ma60: null, inst_streak: 2, vol_ratio: 1 },
  }

  it('no conditions → everything', () => {
    expect(ids(applyFilters(stocks, [], ctx(scores, signals)))).toEqual(['A', 'B', 'C'])
  })

  it('穩健優質 = pass_rate ≥ 75 AND no risk', () => {
    expect(ids(applyFilters(stocks, ['pass75', 'noRisk'], ctx(scores, signals)))).toEqual(['A', 'C'])
  })

  it('轉強起漲 = uptrend AND above MA20 AND 法人連買 ≥ 3', () => {
    expect(ids(applyFilters(stocks, ['uptrend', 'aboveMa20', 'instBuy3'], ctx(scores, signals)))).toEqual(['A'])
  })

  it('低估待買 = P/E < p25 AND pass_rate ≥ 60 AND no risk', () => {
    expect(ids(applyFilters(stocks, ['cheap', 'pass60', 'noRisk'], ctx(scores, signals)))).toEqual(['A'])
  })

  it('量增突破 = vol ratio ≥ 2 AND up today AND above MA60', () => {
    expect(ids(applyFilters(stocks, ['volBurst', 'priceUp', 'aboveMa60'], ctx(scores, signals)))).toEqual(['A'])
  })

  it('null fields never match (C has no daily signals, B has null MA60)', () => {
    expect(ids(applyFilters(stocks, ['aboveMa60'], ctx(scores, signals)))).toEqual(['A'])
    expect(ids(applyFilters(stocks, ['aboveMa20'], ctx(scores, signals)))).toEqual(['A', 'B'])
  })

  it('legacy score entries without pass_rate / risk_score never match score conditions', () => {
    const legacy = { A: { score: 20, max_score: 24 } }
    expect(applyFilters([stock('A')], ['pass60'], ctx(legacy, {}))).toEqual([])
    expect(applyFilters([stock('A')], ['noRisk'], ctx(legacy, {}))).toEqual([])
  })

  it('volume burst uses live volume while market is open', () => {
    const live = [stock('A', { volume: 1000 })]           // 1000 / 400 = 2.5 live
    const sig = { A: { vol_ratio: 0.3, avg_volume_5d: 400 } }
    expect(applyFilters(live, ['volBurst'], ctx({}, sig, true))).toHaveLength(1)
    expect(applyFilters(live, ['volBurst'], ctx({}, sig, false))).toHaveLength(0)
  })

  it('ignores unknown condition keys', () => {
    expect(ids(applyFilters(stocks, ['nope'], ctx(scores, signals)))).toEqual(['A', 'B', 'C'])
  })
})

describe('sortByPotential', () => {
  it('pass_rate desc, then inst_net_5d desc, nulls last', () => {
    const list = [stock('A'), stock('B'), stock('C'), stock('D')]
    const scores = { A: { pass_rate: 70 }, B: { pass_rate: 80 }, C: { pass_rate: 80 } }
    const signals = { B: { inst_net_5d: 10 }, C: { inst_net_5d: 500 } }
    expect(ids(sortByPotential(list, ctx(scores, signals)))).toEqual(['C', 'B', 'A', 'D'])
  })

  it('does not mutate the input', () => {
    const list = [stock('A'), stock('B')]
    sortByPotential(list, ctx({ B: { pass_rate: 90 } }, {}))
    expect(ids(list)).toEqual(['A', 'B'])
  })
})

describe('filterStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('applyPreset replaces the selection; toggle adds/removes', () => {
    const f = useFilterStore()
    f.applyPreset('quality')
    expect(f.active).toEqual(['pass75', 'noRisk'])
    f.toggle('uptrend')
    expect(f.active).toEqual(['pass75', 'noRisk', 'uptrend'])
    f.toggle('pass75')
    expect(f.active).toEqual(['noRisk', 'uptrend'])
  })

  it('persists to localStorage and restores', async () => {
    const f = useFilterStore()
    f.applyPreset('turning')
    await Promise.resolve()
    setActivePinia(createPinia())
    expect(useFilterStore().active).toEqual(['uptrend', 'aboveMa20', 'instBuy3'])
  })

  it('drops unknown keys from corrupted storage', () => {
    localStorage.setItem('stock_filters', JSON.stringify(['pass75', 'bogus']))
    expect(useFilterStore().active).toEqual(['pass75'])
    localStorage.setItem('stock_filters', '{not json')
    setActivePinia(createPinia())
    expect(useFilterStore().active).toEqual([])
  })

  it('clear empties the selection', () => {
    const f = useFilterStore()
    f.applyPreset('value')
    f.clear()
    expect(f.active).toEqual([])
  })
})
