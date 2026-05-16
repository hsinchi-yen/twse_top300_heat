/**
 * colorTier.js — 5-segment color tier mapping (Cyberpunk palette)
 * Taiwan convention: rise = red/crimson, fall = green/teal
 */

export const COLOR_MAP = {
  deep_red:    '#4a0a0a',
  light_red:   '#3a1212',
  neutral:     '#0d1520',
  light_green: '#0a2a1a',
  deep_green:  '#062015',
}

// Neon glow accent per tier (for CSS box-shadow)
export const GLOW_MAP = {
  deep_red:    'rgba(255, 60, 60, 0.5)',
  light_red:   'rgba(255, 100, 100, 0.3)',
  neutral:     'rgba(0, 229, 255, 0.15)',
  light_green: 'rgba(0, 230, 120, 0.3)',
  deep_green:  'rgba(0, 200, 100, 0.5)',
}

// ETF amber cyberpunk palette — same tier logic, amber accent replaces cyan
export const ETF_COLOR_MAP = {
  deep_red:    '#4a1a00',
  light_red:   '#2e1800',
  neutral:     '#111008',
  light_green: '#0a2000',
  deep_green:  '#052015',
}

export const ETF_GLOW_MAP = {
  deep_red:    'rgba(255, 120, 0, 0.5)',
  light_red:   'rgba(255, 165, 0, 0.3)',
  neutral:     'rgba(255, 193, 7, 0.15)',
  light_green: 'rgba(0, 230, 120, 0.3)',
  deep_green:  'rgba(0, 200, 100, 0.5)',
}

/**
 * @param {number} pct - price change percentage
 * @returns {'deep_red'|'light_red'|'neutral'|'light_green'|'deep_green'}
 */
export function getColorTier(pct) {
  if (pct >= 5)  return 'deep_red'
  if (pct >= 1)  return 'light_red'
  if (pct > -1)  return 'neutral'
  if (pct >= -5) return 'light_green'
  return 'deep_green'
}

/**
 * @param {string} tier
 * @returns {string} hex color
 */
export function tierToColor(tier) {
  return COLOR_MAP[tier] ?? COLOR_MAP.neutral
}

/**
 * @param {string} tier
 * @returns {string} rgba glow string
 */
export function tierToGlow(tier) {
  return GLOW_MAP[tier] ?? GLOW_MAP.neutral
}

/** ETF amber variants */
export function etfTierToColor(tier) {
  return ETF_COLOR_MAP[tier] ?? ETF_COLOR_MAP.neutral
}

export function etfTierToGlow(tier) {
  return ETF_GLOW_MAP[tier] ?? ETF_GLOW_MAP.neutral
}
