/**
 * positionSizing.js — 部位試算. Answers "how much can I put in and still know my
 * maximum loss?" — it bounds risk, it does not predict anything. See SPEC.md.
 */

export const LOT_SHARES = 1000
export const DEFAULT_STOP_PCT = 8
const MIN_STOP_PCT = 3
// 手續費 0.1425% × 2 + 證交稅 0.3%, statutory rate before any broker discount.
export const ROUND_TRIP_COST_PCT = 0.1425 * 2 + 0.3

const LIQUIDITY_WARN_PCT = 5
const WIDE_STOP_PCT = 15

const positive = (v) => typeof v === 'number' && Number.isFinite(v) && v > 0

export function defaultStop({ price, ma60 }) {
  if (!positive(price)) return null
  const pctStop = Math.round(price * (100 - DEFAULT_STOP_PCT)) / 100
  // A stop hugging the price fires on noise and inflates the size it justifies.
  const closest = price * (1 - MIN_STOP_PCT / 100)
  if (positive(ma60) && ma60 <= closest && ma60 > pctStop) return { stop: ma60, basis: 'ma60' }
  return { stop: pctStop, basis: 'pct' }
}

/**
 * @returns sizing result, or null when the inputs do not define a long position
 *   with a stop below entry.
 */
export function sizePosition({ capital, riskPct, maxPositionPct, entry, stop, avgVolume }) {
  if (![capital, riskPct, maxPositionPct, entry, stop].every(positive)) return null
  if (stop >= entry) return null

  const riskPerShare = entry - stop
  const byRisk = (capital * riskPct) / 100 / riskPerShare
  const byCap = (capital * maxPositionPct) / 100 / entry
  const limitedBy = byCap < byRisk ? 'cap' : 'risk'
  const allowed = Math.min(byRisk, byCap)

  const lots = Math.floor(allowed / LOT_SHARES)
  const shares = lots >= 1 ? lots * LOT_SHARES : Math.floor(allowed)
  const positionValue = shares * entry
  const maxLoss = shares * riskPerShare
  const participationPct = positive(avgVolume) ? Math.round((shares / avgVolume) * 1000) / 10 : null

  const warnings = []
  if (lots === 0) {
    warnings.push({ key: 'odd_lot', text: '預算不足 1 張，以零股試算，零股流動性較差' })
  }
  if (participationPct !== null && participationPct > LIQUIDITY_WARN_PCT) {
    warnings.push({
      key: 'liquidity',
      text: `部位約占近 5 日均量 ${participationPct}%，進出可能推動價格，建議分批`,
    })
  }
  if ((riskPerShare / entry) * 100 > WIDE_STOP_PCT) {
    warnings.push({ key: 'wide_stop', text: '停損距離超過 15%，觸發時的跌幅已相當大' })
  }

  return {
    lots,
    shares,
    positionValue,
    positionPct: Math.round((positionValue / capital) * 1000) / 10,
    maxLoss,
    maxLossPct: Math.round((maxLoss / capital) * 1000) / 10,
    roundTripCost: Math.round((positionValue * ROUND_TRIP_COST_PCT) / 100),
    participationPct,
    limitedBy,
    warnings,
  }
}
