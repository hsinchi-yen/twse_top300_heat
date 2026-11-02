/** format.js — shared display formatting. Null renders as an em dash, never 0. */

const DASH = '—'
const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

export function formatPrice(p) {
  if (!isNum(p) || p === 0) return DASH
  return p >= 100 ? p.toFixed(1) : p.toFixed(2)
}

export function formatPct(pct, digits = 2) {
  if (!isNum(pct)) return DASH
  return `${pct > 0 ? '+' : ''}${pct.toFixed(digits)}%`
}

export function pctClass(pct) {
  if (!isNum(pct)) return ''
  if (pct > 0) return 'pct-up'
  if (pct < 0) return 'pct-down'
  return 'pct-flat'
}

/** Shares → 張 with Chinese magnitudes. */
export function formatLots(shares) {
  if (!isNum(shares)) return DASH
  const lots = Math.round(shares / 1000)
  if (Math.abs(lots) >= 10000) return `${(lots / 10000).toFixed(1)}萬張`
  return `${lots.toLocaleString('en-US')}張`
}

export function formatSignedLots(lots) {
  if (!isNum(lots)) return DASH
  return `${lots > 0 ? '+' : ''}${Math.round(lots).toLocaleString('en-US')}`
}

export function formatTwd(value) {
  if (!isNum(value)) return DASH
  const abs = Math.abs(value)
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 億`
  if (abs >= 10_000) return `${(value / 10_000).toFixed(1)} 萬`
  return Math.round(value).toLocaleString('en-US')
}

/** A traded stock cannot have zero turnover: a stored 0 means the share count was unknown. */
export function formatTurnover(rate) {
  return isNum(rate) && rate > 0 ? `${rate.toFixed(2)}%` : DASH
}

/** 'YYYY-MM-DD' → 'MM/DD'. */
export function shortDate(date) {
  return typeof date === 'string' && date.length >= 10 ? `${date.slice(5, 7)}/${date.slice(8, 10)}` : (date ?? '')
}

/**
 * Header stamp. `updatedAt` is the API response time, so its clock only describes
 * the data while both fall on the same Taipei day; otherwise the date stands alone.
 */
export function dataTimeLabel(date, updatedAt) {
  const stamp = new Date(updatedAt ?? NaN)
  const day = shortDate(date)
  if (Number.isNaN(stamp.getTime())) return day || DASH
  const zone = { timeZone: 'Asia/Taipei' }
  if (date && stamp.toLocaleDateString('en-CA', zone) !== date) return day
  const time = stamp.toLocaleTimeString('zh-TW', { ...zone, hour12: false, hour: '2-digit', minute: '2-digit' })
  return day ? `${day} ${time}` : time
}
