/**
 * analysis.js — turns the card payloads into a readable assessment.
 *
 * Pure, display-only, derived from the same /api/stocks + /api/scores +
 * /api/signals data the cards use. Two rules hold throughout:
 *   - Missing data stays missing: a dimension without input is null, and null
 *     can never help a stock onto the shortlist.
 *   - Risk outranks score: 排雷 items override a good-looking composite.
 *
 * The weights are editorial heuristics, not fitted to returns, and nothing here
 * has been shown to predict returns. See SPEC.md "Analysis layer".
 */

import { resolveSignal, SIGNALS } from './signals'

export const WEIGHTS = { quality: 0.4, trend: 0.25, flow: 0.2, value: 0.15 }

const LABELS = { quality: '基本面', trend: '趨勢', flow: '籌碼', value: '評價' }

export const STANCES = {
  avoid:         { key: 'avoid',         label: '避開',     hint: '排雷項目達 2 項以上，先排除' },
  insufficient:  { key: 'insufficient',  label: '資料不足', hint: '缺少評分或盤後指標，暫不評估' },
  wait_pullback: { key: 'wait_pullback', label: '等回檔',   hint: '條件不錯但股價離月線偏遠，追高風險較大' },
  candidate:     { key: 'candidate',     label: '研究候選', hint: '條件相對完整，值得進一步研究財報與產業' },
  watch:         { key: 'watch',         label: '觀察',     hint: '部分條件成立，等更多面向轉強' },
  pass:          { key: 'pass',          label: '暫不考慮', hint: '目前多數面向不理想' },
}

const MIN_DIMENSIONS = 3
// Below this a high pass rate means little: 6/6 is a new listing or failed datasets,
// and failed datasets also skip the 排雷 checks.
const MIN_ELIGIBLE = 12
const RISK_PENALTY = 10
const STRETCHED_RATIO = 1.1
const MIN_BREADTH_SAMPLE = 20
const MIN_SECTOR_STOCKS = 3

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))
const lots = (n) => `${n > 0 ? '+' : ''}${Math.round(n).toLocaleString('en-US')}`

function median(values) {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = sorted.length >> 1
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

const enoughCriteria = (score) => isNum(score?.eligible_count) && score.eligible_count >= MIN_ELIGIBLE

function qualityScore(score) {
  if (!isNum(score?.pass_rate) || !enoughCriteria(score)) return null
  return Math.min(100, score.pass_rate + (score.fundamentals_uptrend === true ? 5 : 0))
}

function trendScore(daily) {
  if (!daily) return null
  const hasMa = typeof daily.above_ma20 === 'boolean' || typeof daily.above_ma60 === 'boolean'
  if (!hasMa) return null
  let earned = 0
  let available = 0
  for (const flag of [daily.above_ma20, daily.above_ma60]) {
    if (typeof flag === 'boolean') {
      available += 35
      if (flag) earned += 35
    }
  }
  const fromHigh = daily.pct_from_52w_high
  if (isNum(fromHigh)) {
    available += 30
    earned += fromHigh >= -5 ? 30 : fromHigh >= -15 ? 20 : fromHigh >= -30 ? 10 : 0
  }
  return Math.round((earned / available) * 100)
}

function flowScore(daily) {
  if (!isNum(daily?.inst_streak)) return null
  const net = daily.inst_net_5d
  const tilt = isNum(net) ? Math.sign(net) * 10 : 0
  return clamp(50 + 8 * clamp(daily.inst_streak, -5, 5) + tilt, 0, 100)
}

function valueScore(score) {
  const pe = score?.pe
  if (!pe || !isNum(pe.current) || pe.current <= 0) return null
  if (isNum(pe.p25) && pe.current < pe.p25) return 90
  if (!isNum(pe.median)) return null
  if (pe.current < pe.median) return 65
  return pe.current <= 1.25 * pe.median ? 40 : 20
}

function compositeOf(dimensions, riskScore) {
  const present = dimensions.filter(d => d.score !== null)
  const hasQuality = present.some(d => d.key === 'quality')
  if (!hasQuality || present.length < MIN_DIMENSIONS) return null
  const weight = present.reduce((sum, d) => sum + d.weight, 0)
  const mean = present.reduce((sum, d) => sum + d.score * d.weight, 0) / weight
  return Math.max(0, Math.round(mean - RISK_PENALTY * (riskScore ?? 0)))
}

function stretchPct(stock, daily) {
  const price = stock?.close_price
  if (!isNum(price) || !isNum(daily?.ma20) || daily.ma20 <= 0) return null
  return (price / daily.ma20 - 1) * 100
}

function resolveStance(composite, score, stock, daily) {
  if (resolveSignal(score) === 'avoid' || (score?.risk_score ?? 0) >= 2) return STANCES.avoid
  if (composite === null) return STANCES.insufficient
  const price = stock?.close_price
  const ma20 = daily?.ma20
  const hasLevels = isNum(price) && isNum(ma20)
  // Tolerance: a price at exactly +10% is not "beyond" it once floats are involved.
  if (composite >= 60 && hasLevels && price > ma20 * STRETCHED_RATIO * (1 + 1e-9)) return STANCES.wait_pullback
  if (composite >= 70 && hasLevels && price > ma20) return STANCES.candidate
  return composite >= 55 ? STANCES.watch : STANCES.pass
}

function strengthsOf(score, daily) {
  const out = []
  if (isNum(score?.pass_rate) && score.pass_rate >= 60 && enoughCriteria(score)) {
    const denom = score.eligible_count ?? score.max_score
    out.push(`通過 ${score.score}/${denom} 項基本面條件（${Math.round(score.pass_rate)}%）`)
  }
  if (score?.fundamentals_uptrend === true) out.push('近 3 月營收皆年增，EPS 近 3 季多數成長')
  if (daily?.above_ma20 === true && daily?.above_ma60 === true) out.push('股價站上月線與季線')
  if (isNum(daily?.pct_from_52w_high) && daily.pct_from_52w_high >= -5) {
    out.push(`距 52 週高點 ${daily.pct_from_52w_high}%`)
  }
  if (isNum(daily?.inst_streak) && daily.inst_streak >= 3) {
    const net = isNum(daily.inst_net_5d) ? `，近 5 日 ${lots(daily.inst_net_5d)} 張` : ''
    out.push(`法人連買 ${daily.inst_streak} 日${net}`)
  }
  const pe = score?.pe
  if (pe && isNum(pe.current) && pe.current > 0) {
    if (isNum(pe.p25) && pe.current < pe.p25) out.push(`P/E ${pe.current} 低於 5 年 25 分位 ${pe.p25}`)
    else if (isNum(pe.median) && pe.current < pe.median) out.push(`P/E ${pe.current} 低於 5 年中位數 ${pe.median}`)
  }
  return out
}

function cautionsOf(score, stock, daily) {
  const out = []
  const risk = score?.risk_score
  if (isNum(risk) && risk > 0) {
    const names = (score.risk_flags ?? []).map(f => f.name).filter(Boolean)
    out.push(names.length ? `排雷：${names.join('、')}` : `排雷 ${risk} 項`)
  }
  if (isNum(score?.eligible_count) && !enoughCriteria(score)) {
    out.push(`僅 ${score.eligible_count} 項條件有資料，基本面評分參考性低`)
  }
  if (isNum(score?.pass_rate) && score.pass_rate < 50) {
    out.push(`基本面通過率僅 ${Math.round(score.pass_rate)}%`)
  }
  const stretch = stretchPct(stock, daily)
  if (stretch !== null && stretch > 10) out.push(`股價高於月線 ${stretch.toFixed(1)}%，追高風險較大`)
  if (daily?.above_ma20 === false) out.push('跌破月線')
  if (daily?.above_ma60 === false) out.push('跌破季線')
  if (isNum(daily?.pct_from_52w_high) && daily.pct_from_52w_high <= -20) {
    out.push(`距 52 週高點 ${daily.pct_from_52w_high}%`)
  }
  if (isNum(daily?.inst_streak) && daily.inst_streak <= -3) {
    out.push(`法人連賣 ${Math.abs(daily.inst_streak)} 日`)
  }
  const pe = score?.pe
  if (pe && isNum(pe.current) && isNum(pe.median) && pe.current > pe.median) {
    out.push(`P/E ${pe.current} 高於 5 年中位數 ${pe.median}`)
  }
  return out
}

/** @param {{stock?: object, score?: object|null, daily?: object|null}} input */
export function assessStock({ stock, score = null, daily = null }) {
  const scores = {
    quality: qualityScore(score),
    trend: trendScore(daily),
    flow: flowScore(daily),
    value: valueScore(score),
  }
  const dimensions = Object.keys(WEIGHTS).map(key => ({
    key, label: LABELS[key], weight: WEIGHTS[key], score: scores[key],
  }))
  const composite = compositeOf(dimensions, score?.risk_score)
  return {
    composite,
    dimensions,
    stance: resolveStance(composite, score, stock, daily),
    strengths: strengthsOf(score, daily),
    cautions: cautionsOf(score, stock, daily),
  }
}

const LISTED = new Set(['candidate', 'wait_pullback'])

export function shortlist(pool, { scores, signals }, limit = 12) {
  const netOf = (id) => {
    const net = signals?.[id]?.inst_net_5d
    return isNum(net) ? net : -Infinity
  }
  return pool
    .map(stock => ({
      stock,
      assessment: assessStock({ stock, score: scores?.[stock.stock_id], daily: signals?.[stock.stock_id] }),
    }))
    .filter(row => LISTED.has(row.assessment.stance.key))
    .sort((a, b) =>
      b.assessment.composite - a.assessment.composite
      || netOf(b.stock.stock_id) - netOf(a.stock.stock_id))
    .slice(0, limit)
}

export function marketSummary(pool, { scores, signals }) {
  let advancers = 0
  let decliners = 0
  let unchanged = 0
  let instBuying = 0
  let instSelling = 0
  let instCovered = 0
  let scored = 0
  const counters = { ma20: [0, 0], ma60: [0, 0] }
  const signalCounts = Object.fromEntries(SIGNALS.map(s => [s, 0]))
  const changes = []

  for (const stock of pool) {
    const change = stock.price_change_pct
    if (isNum(change)) {
      changes.push(change)
      if (change > 0) advancers++
      else if (change < 0) decliners++
      else unchanged++
    }
    const daily = signals?.[stock.stock_id]
    if (typeof daily?.above_ma20 === 'boolean') {
      counters.ma20[0]++
      if (daily.above_ma20) counters.ma20[1]++
    }
    if (typeof daily?.above_ma60 === 'boolean') {
      counters.ma60[0]++
      if (daily.above_ma60) counters.ma60[1]++
    }
    if (isNum(daily?.inst_streak)) {
      instCovered++
      if (daily.inst_streak >= 3) instBuying++
      else if (daily.inst_streak <= -3) instSelling++
    }
    const signal = resolveSignal(scores?.[stock.stock_id])
    if (signal) {
      signalCounts[signal]++
      scored++
    }
  }

  const share = ([total, hit]) => (total >= MIN_BREADTH_SAMPLE ? Math.round((hit / total) * 1000) / 10 : null)
  return {
    total: pool.length,
    advancers,
    decliners,
    unchanged,
    medianChange: median(changes),
    pctAboveMa20: share(counters.ma20),
    pctAboveMa60: share(counters.ma60),
    instBuying: instCovered ? instBuying : null,
    instSelling: instCovered ? instSelling : null,
    signalCounts,
    scored,
  }
}

const MARKET_READS = [
  { min: 70, key: 'hot',      label: '偏熱', text: '多數股票在月線之上，趨勢強但已偏熱，追價的風險報酬比較差。' },
  { min: 50, key: 'positive', label: '偏多', text: '過半股票在月線之上，環境偏有利，個股條件仍是關鍵。' },
  { min: 30, key: 'mixed',    label: '分歧', text: '多空分歧，個股表現差異大。' },
  { min: 0,  key: 'weak',     label: '偏弱', text: '多數股票跌破月線，環境不利，下跌風險較高。' },
]

export function marketRead({ pctAboveMa20 }) {
  if (!isNum(pctAboveMa20)) return null
  return MARKET_READS.find(r => pctAboveMa20 >= r.min) ?? null
}

/** Live per-sector view from the pool; multi-day returns come from /api/market/trend. */
export function sectorSnapshot(pool, { scores }) {
  const groups = new Map()
  for (const stock of pool) {
    if (!stock.sector || stock.sector === '其他') continue
    if (!groups.has(stock.sector)) groups.set(stock.sector, [])
    groups.get(stock.sector).push(stock)
  }
  const out = []
  for (const [name, stocks] of groups) {
    if (stocks.length < MIN_SECTOR_STOCKS) continue
    const changes = stocks.map(s => s.price_change_pct).filter(isNum)
    const rates = stocks.map(s => scores?.[s.stock_id]?.pass_rate).filter(isNum)
    const leader = stocks.reduce((best, s) => (
      isNum(s.price_change_pct) && (best === null || s.price_change_pct > best.price_change_pct) ? s : best
    ), null)
    out.push({
      name,
      count: stocks.length,
      medianChange: median(changes),
      upShare: changes.length ? (changes.filter(c => c > 0).length / changes.length) * 100 : null,
      avgPassRate: rates.length ? rates.reduce((a, b) => a + b, 0) / rates.length : null,
      leader,
    })
  }
  return out.sort((a, b) => (b.medianChange ?? -Infinity) - (a.medianChange ?? -Infinity))
}

/**
 * Rebase several histories to 100 on the dates they all share, so stocks with
 * different listing dates or suspensions compare over the same window.
 * @param {Array<{id: string, bars: Array<{date: string, close: number}>}>} histories
 * @returns {{dates: string[], series: Array<{id: string, values: number[]}>}}
 */
export function rebasedComparison(histories) {
  if (!histories.length) return { dates: [], series: [] }
  const maps = histories.map(h => new Map(h.bars.filter(b => isNum(b.close) && b.close > 0).map(b => [b.date, b.close])))
  const dates = [...maps[0].keys()].filter(d => maps.every(m => m.has(d))).sort()
  if (!dates.length) return { dates: [], series: [] }
  const series = histories.map((h, i) => {
    const base = maps[i].get(dates[0])
    return { id: h.id, values: dates.map(d => Math.round((maps[i].get(d) / base) * 10000) / 100) }
  })
  return { dates, series }
}

/** Reasons to re-check something already on the watchlist. */
export function watchAlerts({ stock, score = null, daily = null }) {
  const alerts = []
  const risk = score?.risk_score
  if (isNum(risk) && risk > 0) {
    const names = (score.risk_flags ?? []).map(f => f.name).filter(Boolean)
    alerts.push({ key: 'risk', label: names.length ? `排雷：${names.join('、')}` : `排雷 ${risk} 項` })
  }
  const price = stock?.close_price
  if (isNum(price) && isNum(daily?.ma60) && price < daily.ma60) {
    alerts.push({ key: 'below_ma60', label: `跌破季線 ${daily.ma60}` })
  } else if (isNum(price) && isNum(daily?.ma20) && price < daily.ma20) {
    alerts.push({ key: 'below_ma20', label: `跌破月線 ${daily.ma20}` })
  }
  if (isNum(daily?.inst_streak) && daily.inst_streak <= -3) {
    alerts.push({ key: 'inst_selling', label: `法人連賣 ${Math.abs(daily.inst_streak)} 日` })
  }
  if (isNum(daily?.pct_from_52w_high) && daily.pct_from_52w_high <= -20) {
    alerts.push({ key: 'drawdown', label: `距高點 ${daily.pct_from_52w_high}%` })
  }
  return alerts
}
