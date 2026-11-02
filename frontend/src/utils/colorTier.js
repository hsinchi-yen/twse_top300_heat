/**
 * colorTier.js — 5-segment heat tier mapping.
 * Taiwan convention: rise = red, fall = green.
 *
 * Values reference CSS custom properties from tokens.css so the theme can flip
 * without touching JS. ETF cards share the same tiers as stock cards.
 */

export const COLOR_MAP = {
  deep_red:    'var(--tier-dr-bg)',
  light_red:   'var(--tier-lr-bg)',
  neutral:     'var(--tier-nt-bg)',
  light_green: 'var(--tier-lg-bg)',
  deep_green:  'var(--tier-dg-bg)',
}

export const BORDER_MAP = {
  deep_red:    'var(--tier-dr-border)',
  light_red:   'var(--tier-lr-border)',
  neutral:     'var(--tier-nt-border)',
  light_green: 'var(--tier-lg-border)',
  deep_green:  'var(--tier-dg-border)',
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

/** @returns {string} CSS var reference for background */
export function tierToColor(tier) {
  return COLOR_MAP[tier] ?? COLOR_MAP.neutral
}

/** @returns {string} CSS var reference for border */
export function tierToBorder(tier) {
  return BORDER_MAP[tier] ?? BORDER_MAP.neutral
}
