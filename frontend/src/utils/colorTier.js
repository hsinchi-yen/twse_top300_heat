/**
 * colorTier.js — 5-segment color tier mapping
 * Taiwan convention: rise = red/crimson, fall = green/teal
 *
 * All color values reference CSS custom properties from tokens.css so that
 * the theme system can flip dark/light without touching JS.
 */

export const COLOR_MAP = {
  deep_red:    'var(--tier-dr-bg)',
  light_red:   'var(--tier-lr-bg)',
  neutral:     'var(--tier-nt-bg)',
  light_green: 'var(--tier-lg-bg)',
  deep_green:  'var(--tier-dg-bg)',
}

export const GLOW_MAP = {
  deep_red:    'var(--tier-dr-glow)',
  light_red:   'var(--tier-lr-glow)',
  neutral:     'var(--tier-nt-glow)',
  light_green: 'var(--tier-lg-glow)',
  deep_green:  'var(--tier-dg-glow)',
}

export const BORDER_MAP = {
  deep_red:    'var(--tier-dr-border)',
  light_red:   'var(--tier-lr-border)',
  neutral:     'var(--tier-nt-border)',
  light_green: 'var(--tier-lg-border)',
  deep_green:  'var(--tier-dg-border)',
}

// ETF amber palette — same tier logic, amber/orange accent
export const ETF_COLOR_MAP = {
  deep_red:    'var(--etf-dr-bg)',
  light_red:   'var(--etf-lr-bg)',
  neutral:     'var(--etf-nt-bg)',
  light_green: 'var(--etf-lg-bg)',
  deep_green:  'var(--etf-dg-bg)',
}

export const ETF_GLOW_MAP = {
  deep_red:    'var(--etf-dr-glow)',
  light_red:   'var(--etf-lr-glow)',
  neutral:     'var(--etf-nt-glow)',
  light_green: 'var(--etf-lg-glow)',
  deep_green:  'var(--etf-dg-glow)',
}

export const ETF_BORDER_MAP = {
  deep_red:    'var(--etf-dr-border)',
  light_red:   'var(--etf-lr-border)',
  neutral:     'var(--etf-nt-border)',
  light_green: 'var(--etf-lg-border)',
  deep_green:  'var(--etf-dg-border)',
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

/** @returns {string} CSS var reference for glow */
export function tierToGlow(tier) {
  return GLOW_MAP[tier] ?? GLOW_MAP.neutral
}

/** @returns {string} CSS var reference for border */
export function tierToBorder(tier) {
  return BORDER_MAP[tier] ?? BORDER_MAP.neutral
}

/** ETF amber variants */
export function etfTierToColor(tier) {
  return ETF_COLOR_MAP[tier] ?? ETF_COLOR_MAP.neutral
}

export function etfTierToGlow(tier) {
  return ETF_GLOW_MAP[tier] ?? ETF_GLOW_MAP.neutral
}

export function etfTierToBorder(tier) {
  return ETF_BORDER_MAP[tier] ?? ETF_BORDER_MAP.neutral
}
