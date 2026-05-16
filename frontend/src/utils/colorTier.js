/**
 * colorTier.js — 5-segment color tier mapping
 * Pure function — no side effects, fully unit-testable.
 *
 * Taiwan convention: rise = red, fall = green
 */

export const COLOR_MAP = {
  deep_red:    '#C62828',
  light_red:   '#EF5350',
  neutral:     '#424242',
  light_green: '#43A047',
  deep_green:  '#1B5E20',
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
