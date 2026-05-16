/**
 * colorTier.test.js — /tdd tests for colorTier utility
 */

import { describe, it, expect } from 'vitest'
import { getColorTier, tierToColor, COLOR_MAP } from '../src/utils/colorTier'

describe('getColorTier', () => {
  it('returns deep_red for pct >= 5', () => {
    expect(getColorTier(5)).toBe('deep_red')
    expect(getColorTier(7)).toBe('deep_red')
    expect(getColorTier(10)).toBe('deep_red')
  })

  it('returns light_red for 1 <= pct < 5', () => {
    expect(getColorTier(1)).toBe('light_red')
    expect(getColorTier(3)).toBe('light_red')
    expect(getColorTier(4.99)).toBe('light_red')
  })

  it('returns neutral for -1 < pct < 1', () => {
    expect(getColorTier(0)).toBe('neutral')
    expect(getColorTier(0.99)).toBe('neutral')
    expect(getColorTier(-0.99)).toBe('neutral')
  })

  it('returns light_green for -5 <= pct <= -1', () => {
    expect(getColorTier(-1)).toBe('light_green')
    expect(getColorTier(-3)).toBe('light_green')
    expect(getColorTier(-5)).toBe('light_green')
  })

  it('returns deep_green for pct < -5', () => {
    expect(getColorTier(-5.01)).toBe('deep_green')
    expect(getColorTier(-10)).toBe('deep_green')
  })
})

describe('tierToColor', () => {
  it('maps each tier to a hex color', () => {
    expect(tierToColor('deep_red')).toBe(COLOR_MAP.deep_red)
    expect(tierToColor('light_red')).toBe(COLOR_MAP.light_red)
    expect(tierToColor('neutral')).toBe(COLOR_MAP.neutral)
    expect(tierToColor('light_green')).toBe(COLOR_MAP.light_green)
    expect(tierToColor('deep_green')).toBe(COLOR_MAP.deep_green)
  })

  it('returns neutral color for unknown tier', () => {
    expect(tierToColor('unknown')).toBe(COLOR_MAP.neutral)
  })
})
