/**
 * colorTier.js — 5-segment color tier mapping (Cyberpunk palette)
 * Taiwan convention: rise = red/crimson, fall = green/teal
 */

export const COLOR_MAP = {
  deep_red:    '#4a0a0a',   // deep crimson — limit up
  light_red:   '#3a1212',   // dark rose — moderate rise
  neutral:     '#0d1520',   // deep navy — flat
  light_green: '#0a2a1a',   // dark forest — moderate fall
  deep_green:  '#062015',   // deep teal — limit down
}

// Neon glow accent per tier (for CSS box-shadow)
export const GLOW_MAP = {
  deep_red:    'rgba(255, 60, 60, 0.5)',
  light_red:   'rgba(255, 100, 100, 0.3)',
  neutral:     'rgba(0, 229, 255, 0.15)',
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
