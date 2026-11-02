/**
 * positionSizing.test.js — 部位試算. The point of this module is to bound the loss
 * on a large allocation, so the bounds are what is tested.
 */

import { describe, it, expect } from 'vitest'
import { defaultStop, sizePosition, ROUND_TRIP_COST_PCT } from '../src/utils/positionSizing'

const base = { capital: 10_000_000, riskPct: 1, maxPositionPct: 20, entry: 100, stop: 90, avgVolume: 50_000_000 }

describe('defaultStop', () => {
  it('uses the quarterly line when it is the closer floor', () => {
    expect(defaultStop({ price: 100, ma60: 95 })).toEqual({ stop: 95, basis: 'ma60' })
  })

  it('ignores a quarterly line so close that ordinary noise would trigger it', () => {
    expect(defaultStop({ price: 100, ma60: 99.7 })).toEqual({ stop: 92, basis: 'pct' })
    expect(defaultStop({ price: 100, ma60: 97.5 })).toEqual({ stop: 92, basis: 'pct' })
    expect(defaultStop({ price: 100, ma60: 97 })).toEqual({ stop: 97, basis: 'ma60' })
  })

  it('falls back to -8% when the quarterly line is far away', () => {
    expect(defaultStop({ price: 100, ma60: 70 })).toEqual({ stop: 92, basis: 'pct' })
  })

  it('falls back to -8% when the price is under the quarterly line', () => {
    expect(defaultStop({ price: 100, ma60: 110 })).toEqual({ stop: 92, basis: 'pct' })
  })

  it('falls back to -8% without a quarterly line', () => {
    expect(defaultStop({ price: 100, ma60: null })).toEqual({ stop: 92, basis: 'pct' })
  })

  it('returns null without a price', () => {
    expect(defaultStop({ price: null, ma60: 90 })).toBe(null)
    expect(defaultStop({ price: 0, ma60: 90 })).toBe(null)
  })
})

describe('sizePosition', () => {
  it('sizes by risk: a stop-out loses the risk budget', () => {
    const p = sizePosition(base)
    // 100,000 risk ÷ 10 per share = 10,000 shares = 10 張
    expect(p).toMatchObject({ lots: 10, shares: 10_000, positionValue: 1_000_000, maxLoss: 100_000, limitedBy: 'risk' })
    expect(p.positionPct).toBe(10)
    expect(p.maxLossPct).toBe(1)
  })

  it('never exceeds the single-position cap, however tight the stop', () => {
    const p = sizePosition({ ...base, stop: 99.5 })
    expect(p).toMatchObject({ lots: 20, shares: 20_000, positionValue: 2_000_000, limitedBy: 'cap' })
    expect(p.positionPct).toBe(20)
  })

  it('floors to whole lots so the risk budget is never exceeded', () => {
    const p = sizePosition({ ...base, stop: 97 })
    expect(p.lots).toBe(20)
    const q = sizePosition({ ...base, capital: 1_000_000, maxPositionPct: 100, stop: 97 })
    // 10,000 risk ÷ 3 = 3,333 → 3 張
    expect(q.lots).toBe(3)
    expect(q.maxLoss).toBeLessThanOrEqual(10_000)
  })

  it('uses odd lots when the budget buys less than one lot', () => {
    const p = sizePosition({ ...base, capital: 500_000, entry: 1000, stop: 900 })
    expect(p.lots).toBe(0)
    expect(p.shares).toBe(50)
    expect(p.warnings.map(w => w.key)).toContain('odd_lot')
  })

  it('warns when the order is large against daily volume', () => {
    const quiet = sizePosition({ ...base, avgVolume: 100_000 })
    expect(quiet.participationPct).toBe(10)
    expect(quiet.warnings.map(w => w.key)).toContain('liquidity')
    expect(sizePosition(base).warnings.map(w => w.key)).not.toContain('liquidity')
  })

  it('reports unknown liquidity as null, not zero', () => {
    const p = sizePosition({ ...base, avgVolume: null })
    expect(p.participationPct).toBe(null)
    expect(p.warnings.map(w => w.key)).not.toContain('liquidity')
  })

  it('includes statutory round-trip cost', () => {
    expect(ROUND_TRIP_COST_PCT).toBeCloseTo(0.585)
    expect(sizePosition(base).roundTripCost).toBe(5850)
  })

  it('warns about a very wide stop', () => {
    expect(sizePosition({ ...base, stop: 80 }).warnings.map(w => w.key)).toContain('wide_stop')
    expect(sizePosition(base).warnings.map(w => w.key)).not.toContain('wide_stop')
  })

  it.each([
    ['capital is zero', { capital: 0 }],
    ['risk is zero', { riskPct: 0 }],
    ['cap is zero', { maxPositionPct: 0 }],
    ['entry is missing', { entry: null }],
    ['stop is missing', { stop: null }],
    ['stop is above entry', { stop: 110 }],
    ['stop equals entry', { stop: 100 }],
    ['stop is negative', { stop: -1 }],
    ['risk is not a number', { riskPct: NaN }],
  ])('returns null when %s', (_, over) => {
    expect(sizePosition({ ...base, ...over })).toBe(null)
  })
})
