/**
 * signals.js — derive card signal / pass rate / indicator chips from a buy-score
 * summary entry (GET /api/scores).
 *
 * Legacy score files carry only {score, max_score, fundamentals_uptrend}; any
 * missing field hides its UI. Nothing here invents a fallback number.
 *
 * Signal colours deliberately avoid red/green (Taiwan: red = up, green = down):
 * strong_buy 金 · buy 青 · watch 灰藍 · neutral 暗灰 · avoid 紫 (see tokens.css).
 */

export const SIGNALS = ['strong_buy', 'buy', 'watch', 'neutral', 'avoid']

const AVOID_LABEL = '高風險避開'

/** @returns {'strong_buy'|'buy'|'watch'|'neutral'|'avoid'|null} */
export function resolveSignal(buyScore) {
  const raw = buyScore?.signal
  if (!raw) return null
  if (buyScore.signal_label === AVOID_LABEL || (buyScore.risk_score ?? 0) >= 2) return 'avoid'
  return SIGNALS.includes(raw) ? raw : null
}

export function signalLabel(buyScore) {
  if (!resolveSignal(buyScore)) return null
  return buyScore.signal_label ?? null
}

/** pass_rate as served; null when absent (never derived from score/max_score). */
export function passRate(buyScore) {
  const r = buyScore?.pass_rate
  return typeof r === 'number' && Number.isFinite(r) ? r : null
}

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

/**
 * Chips from the monthly buy-score summary.
 * chip: {key, icon, text, title, tone, keepText}
 *   tone: 'good' | 'soft' | 'warn' | 'up' | 'down'
 *   keepText: text stays visible on compact cards (icon-only otherwise)
 */
export function scoreChips(buyScore) {
  if (!buyScore) return []
  const chips = []

  if (buyScore.fundamentals_uptrend === true) {
    chips.push({
      key: 'uptrend', icon: '✅', text: '轉強', tone: 'good', keepText: false,
      title: '近3月營收年增率轉正 + EPS YoY 3季中2季以上正成長',
    })
  }

  const pe = buyScore.pe
  if (pe && isNum(pe.current)) {
    if (isNum(pe.p25) && pe.current < pe.p25) {
      chips.push({
        key: 'value', icon: '💲', text: '低估', tone: 'good', keepText: false,
        title: `P/E ${pe.current} < 近5年 25 分位 ${pe.p25}`,
      })
    } else if (isNum(pe.median) && pe.current < pe.median) {
      chips.push({
        key: 'value', icon: '💲', text: '偏低', tone: 'soft', keepText: false,
        title: `P/E ${pe.current} < 近5年中位數 ${pe.median}`,
      })
    }
  }

  const risk = buyScore.risk_score
  if (isNum(risk) && risk > 0) {
    const names = (buyScore.risk_flags ?? []).map(f => f.name).filter(Boolean)
    chips.push({
      key: 'risk', icon: '⚠', text: String(risk), tone: 'warn', keepText: true,
      title: names.length ? `排雷：${names.join('、')}` : `排雷 ${risk} 項`,
    })
  }

  return chips
}

const fmtLots = (n) => `${n > 0 ? '+' : ''}${Math.round(n).toLocaleString('en-US')}`

/**
 * 量比: while the market is open, today's running volume ÷ the 5-day average;
 * otherwise the nightly value. Shared by chips and the 量增突破 filter.
 * @returns {{ratio: number|null, live: boolean}}
 */
export function volumeRatio(sig, stock, marketOpen) {
  if (!sig) return { ratio: null, live: false }
  const live = Boolean(marketOpen) && isNum(stock?.volume) && isNum(sig.avg_volume_5d) && sig.avg_volume_5d > 0
  const ratio = live ? stock.volume / sig.avg_volume_5d : sig.vol_ratio
  return { ratio: isNum(ratio) ? ratio : null, live }
}

/**
 * Chips from the nightly 籌碼 / 技術 indicators (GET /api/signals).
 * stock: the live quote (volume) — while the market is open the volume ratio
 * uses today's running volume ÷ the 5-day average; after close the nightly value.
 * Institutional chips follow Taiwan colours: 連買 = up (red), 連賣 = down (green).
 */
export function dailyChips(sig, stock, marketOpen) {
  if (!sig) return []
  const chips = []

  const streak = sig.inst_streak
  if (isNum(streak) && Math.abs(streak) >= 2) {
    const net5 = isNum(sig.inst_net_5d) ? `｜近5日 ${fmtLots(sig.inst_net_5d)} 張` : ''
    chips.push({
      key: 'inst', icon: '法', text: `${streak > 0 ? '+' : ''}${streak}`,
      tone: streak > 0 ? 'up' : 'down', keepText: true,
      title: `外資+投信 連${streak > 0 ? '買' : '賣'} ${Math.abs(streak)} 日${net5}`,
    })
  }

  if (sig.above_ma20 === true) {
    const both = sig.above_ma60 === true
    chips.push({
      key: 'ma', icon: '📈', text: both ? '月季線上' : '月線上', tone: 'up', keepText: false,
      title: `收盤 ${sig.close} ／ MA20 ${sig.ma20}${isNum(sig.ma60) ? ` ／ MA60 ${sig.ma60}` : ''}`,
    })
  }

  const { ratio, live } = volumeRatio(sig, stock, marketOpen)
  if (ratio !== null && ratio >= 1.5) {
    chips.push({
      key: 'vol', icon: '量', text: `×${ratio.toFixed(1)}`, tone: 'good', keepText: true,
      title: `${live ? '盤中' : '盤後'}量比 ${ratio.toFixed(2)}（÷ 前5日均量）`,
    })
  }

  const fromHigh = sig.pct_from_52w_high
  if (isNum(fromHigh) && fromHigh >= -5) {
    chips.push({
      key: 'high', icon: '🔝', text: fromHigh === 0 ? '創高' : `距高${fromHigh}%`, tone: 'good', keepText: false,
      title: `52週收盤高點 ${sig.high_52w}`,
    })
  }

  return chips
}
