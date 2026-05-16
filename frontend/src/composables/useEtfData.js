/**
 * useEtfData.js — ETF data polling composable
 *
 * Phase A: MOCK_MODE = true → uses static mock data for UI development.
 * Phase C: set MOCK_MODE = false → polls real /api/etf endpoint.
 *
 * Polling logic mirrors useStockData: 60s interval, stops after market close,
 * re-fetches immediately when etfSortBy changes.
 */

import { watch, onUnmounted } from 'vue'
import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const POLL_INTERVAL_MS = 60_000
const MAX_BACKOFF_MS = 300_000
const MOCK_MODE = false  // Phase C: real /api/etf endpoint

// ── 100-ETF mock dataset (representative Taiwan ETFs) ──
const MOCK_ETFS = (() => {
  const raw = [
    // [etf_id, name, etf_type, asset_scale(億), outstanding_units, close_price, price_change_pct, nav, management_fee]
    ['00631L', '元大台灣50正2',  '槓桿/反向', 320.5,  210000000,  85.30,  3.12, 85.10, 1.00],
    ['00632R', '元大台灣50反1',  '槓桿/反向',  52.1,   85000000,  12.48, -2.30, 12.52, 1.00],
    ['0050',   '元大台灣50',     '股票型',   3241.5, 1680000000, 185.50,  1.23, 185.20, 0.32],
    ['0056',   '元大高股息',     '股票型',   1832.0, 3560000000,  38.82,  0.72,  38.74, 0.66],
    ['00878',  '國泰永續高股息', '股票型',   2105.3, 6230000000,  22.06,  0.92,  22.01, 0.25],
    ['00929',  '復華台灣科技優息','股票型',   1245.6, 3890000000,  20.15,  1.54,  20.08, 0.25],
    ['006208', '富邦台灣50',     '股票型',    762.4,  385000000, 125.40,  1.18, 125.10, 0.15],
    ['00679B', '元大美債20年',   '債券型',    890.2,  450000000,  32.12, -0.56,  32.20, 0.15],
    ['00687B', '國泰20年美債',   '債券型',    345.8,  185000000,  37.48, -0.42,  37.55, 0.20],
    ['00720B', '元大投資級公司債','債券型',    212.3,  120000000,  39.75, -0.18,  39.80, 0.25],
    ['00635U', '元大S&P黃金',    '商品型',    145.2,   82000000,  28.54,  0.85,  28.48, 0.34],
    ['00642U', '元大S&P石油',    '商品型',     38.7,   55000000,  12.20, -1.45,  12.25, 0.99],
    ['00830',  '國泰費城半導體', '股票型',    425.6,  280000000,  63.15,  2.15,  62.90, 0.45],
    ['00881',  '國泰台灣5G+',    '股票型',    316.8,  320000000,  16.85,  1.62,  16.78, 0.45],
    ['00891',  '中信關鍵半導體', '股票型',    228.4,  252000000,  17.22,  1.89,  17.15, 0.45],
    ['00893',  '國泰智能電動車', '股票型',    185.6,  268000000,  14.38,  0.98,  14.32, 0.45],
    ['00896',  '中信綠能及電動車','股票型',   142.3,  220000000,  15.12,  1.25,  15.07, 0.45],
    ['00900',  '富邦特選高股息30','股票型',   489.2,  682000000,  19.85,  0.76,  19.79, 0.30],
    ['00905',  '華南永昌台灣優息', '股票型',   95.4,  185000000,  14.56,  0.62,  14.51, 0.50],
    ['00907',  '永豐台灣ESG',    '股票型',    112.8,  195000000,  17.30,  0.82,  17.24, 0.45],
    ['00915',  '凱基優選高股息30','股票型',   320.5,  485000000,  18.52,  1.08,  18.46, 0.25],
    ['00918',  '大華優利高填息30','股票型',   265.3,  420000000,  17.85,  0.95,  17.80, 0.30],
    ['00919',  '群益台灣精選高息','股票型',   1568.4, 2860000000,  19.82,  1.32,  19.76, 0.25],
    ['00921',  '兆豐龍頭等權重', '股票型',   158.6,  280000000,  18.45,  1.02,  18.39, 0.40],
    ['00922',  '國泰台灣產業龍頭','股票型',   198.3,  325000000,  18.92,  0.88,  18.86, 0.40],
    ['00923',  '群益台科半導體', '股票型',    285.4,  418000000,  20.15,  1.65,  20.08, 0.35],
    ['00924',  '永豐優息存股',   '股票型',    145.8,  252000000,  17.35,  0.72,  17.29, 0.40],
    ['00925',  '凱基金融高息創新','股票型',    98.2,  180000000,  15.68,  0.45,  15.63, 0.45],
    ['00926',  '凱基優選龍頭等重','股票型',   112.5,  198000000,  16.82,  0.58,  16.77, 0.40],
    ['00927',  '群益半導體收益', '股票型',    325.6,  512000000,  18.95,  1.42,  18.89, 0.35],
    ['00928',  '中信全球電動車', '股票型',     85.3,  162000000,  14.25,  1.12,  14.20, 0.50],
    ['00930',  '永豐智能車供應鏈','股票型',    72.8,  145000000,  14.85,  0.95,  14.80, 0.50],
    ['00931',  '兆豐台灣晶圓製造','股票型',   185.4,  298000000,  18.62,  1.38,  18.56, 0.45],
    ['00932',  '兆豐永續高息等重','股票型',   142.6,  238000000,  17.45,  0.68,  17.39, 0.40],
    ['00933',  '國泰台灣領袖50', '股票型',    268.5,  428000000,  19.35,  1.05,  19.29, 0.35],
    ['00934',  '中信成長高股息', '股票型',    312.8,  498000000,  18.75,  0.88,  18.69, 0.35],
    ['00935',  '野村台灣新科技50','股票型',   158.3,  265000000,  17.92,  1.28,  17.86, 0.45],
    ['00936',  '台新臺灣IC設計',  '股票型',   125.6,  215000000,  17.35,  1.15,  17.29, 0.45],
    ['00937B', '台新ESG投資級債', '債券型',   185.2,  252000000,  20.15, -0.25,  20.20, 0.25],
    ['00938',  '永豐台灣ESG優質', '股票型',   95.4,  168000000,  16.82,  0.75,  16.76, 0.45],
    ['00939',  '統一台灣高息動能','股票型',   425.8,  668000000,  19.15,  1.12,  19.09, 0.30],
    ['00940',  '元大台灣價值高息','股票型',   856.4, 1325000000,  18.65,  0.95,  18.59, 0.25],
    ['00941',  '台新臺灣5G關鍵', '股票型',    68.5,  128000000,  15.82,  1.05,  15.77, 0.50],
    ['00942B', '第一金10年以上IG債','債券型',  125.3,  185000000,  20.35, -0.15,  20.38, 0.25],
    ['00943',  '兆豐台灣低波動', '股票型',    85.6,  158000000,  16.45,  0.52,  16.40, 0.45],
    ['00944',  '群益台灣ESG低碳', '股票型',   72.3,  135000000,  15.95,  0.62,  15.90, 0.50],
    ['00945B', '統一美債20年',   '債券型',    235.8,  325000000,  21.45, -0.32,  21.52, 0.20],
    ['00946',  '元大台灣高息低波','股票型',   398.5,  625000000,  18.85,  0.78,  18.79, 0.30],
    ['00947',  '大華優選金融',   '股票型',    58.4,  112000000,  15.35,  0.45,  15.30, 0.50],
    ['00948',  '野村台灣創新科技','股票型',    85.2,  158000000,  16.15,  0.98,  16.10, 0.45],
    ['00949',  '台新MSCI台灣',   '股票型',    125.8,  212000000,  18.35,  1.02,  18.29, 0.40],
    ['00950',  '凱基台灣精選藍籌','股票型',   95.6,  172000000,  16.85,  0.72,  16.80, 0.45],
    ['00951',  '永豐台灣高息龍頭','股票型',   185.4,  298000000,  18.25,  0.85,  18.19, 0.40],
    ['00952',  '群益電動車關鍵材料','股票型',  42.5,   85000000,  14.65,  1.25,  14.60, 0.50],
    ['00953B', '中信優先金融債',  '債券型',   145.2,  205000000,  20.85, -0.18,  20.89, 0.25],
    ['00954',  '兆豐台灣高息成長','股票型',   215.6,  342000000,  18.45,  0.92,  18.39, 0.35],
    ['00955B', '富邦全球投資級債','債券型',   168.3,  238000000,  21.15, -0.22,  21.20, 0.25],
    ['00956',  '台新台灣高息成長','股票型',   125.8,  212000000,  17.65,  0.82,  17.59, 0.40],
    ['00957',  '富邦台灣半導體',  '股票型',   285.4,  425000000,  19.75,  1.48,  19.69, 0.35],
    ['00958',  '永豐ESG優質高息','股票型',   98.5,  178000000,  16.35,  0.65,  16.30, 0.45],
    ['00959',  '國泰台灣領先',   '股票型',    168.3,  278000000,  18.15,  0.88,  18.09, 0.40],
    ['00960',  '富邦台灣優質高息','股票型',   212.5,  338000000,  18.55,  0.95,  18.49, 0.35],
    ['00961',  '元大生技醫療',   '股票型',     72.8,  138000000,  15.25,  0.58,  15.20, 0.50],
    ['00962',  '凱基台灣ESG永續','股票型',    85.4,  158000000,  16.45,  0.68,  16.40, 0.45],
    ['00963',  '群益台灣優質高息','股票型',   145.6,  242000000,  17.85,  0.78,  17.79, 0.40],
    ['00964',  '統一台灣ESG',    '股票型',    95.2,  172000000,  16.75,  0.62,  16.70, 0.45],
    ['00965',  '中信台灣智慧50', '股票型',   125.8,  212000000,  17.35,  1.02,  17.29, 0.40],
    ['00966',  '兆豐半導體高息', '股票型',   185.4,  298000000,  18.65,  1.25,  18.59, 0.35],
    ['00967',  '永豐全球AI關鍵',  '股票型',   98.5,  178000000,  16.85,  1.38,  16.79, 0.50],
    ['00968',  '台新全球AI領導', '股票型',    72.3,  135000000,  15.95,  1.15,  15.90, 0.50],
    ['00969',  '富邦全球AI半導體','股票型',   145.6,  242000000,  18.25,  1.42,  18.19, 0.45],
    ['00970',  '國泰AI晶片半導體','股票型',   215.8,  342000000,  18.85,  1.58,  18.79, 0.40],
    ['00971',  '元大全球AI科技',  '股票型',   185.4,  298000000,  19.25,  1.65,  19.19, 0.45],
    ['00972',  '凱基AI明星',     '股票型',    125.6,  212000000,  17.85,  1.35,  17.79, 0.45],
    ['00973B', '群益投資級科技債','債券型',    98.2,  158000000,  20.15, -0.12,  20.18, 0.30],
    ['00974',  '中信AI半導體',   '股票型',    168.3,  268000000,  18.45,  1.52,  18.39, 0.40],
    ['00975',  '統一AI關鍵股',   '股票型',    85.4,  158000000,  16.95,  1.28,  16.89, 0.50],
    ['00976',  '野村AI科技',     '股票型',    112.5,  195000000,  17.65,  1.42,  17.59, 0.45],
    ['00977',  '兆豐AI優選',     '股票型',    95.6,  172000000,  17.15,  1.18,  17.09, 0.45],
    ['00978',  '永豐AI領袖',     '股票型',    78.3,  148000000,  16.45,  1.05,  16.40, 0.50],
    ['00979',  '台新AI精選',     '股票型',    65.2,  125000000,  15.85,  0.95,  15.80, 0.50],
    ['00980',  '富邦台灣IC設計', '股票型',   145.8,  245000000,  18.15,  1.35,  18.09, 0.40],
    ['00981A', '元大AI收益成長A', '股票型',   285.4,  425000000,  19.45,  1.62,  19.39, 0.45],
    ['00982',  '國泰台灣半導體', '股票型',   198.6,  318000000,  18.75,  1.45,  18.69, 0.40],
    ['00983B', '中信全球投資級債','債券型',   125.3,  185000000,  20.25, -0.15,  20.29, 0.25],
    ['00984',  '凱基全球AI晶片', '股票型',    95.4,  172000000,  17.35,  1.28,  17.29, 0.45],
    ['00985',  '群益AI優選',     '股票型',   112.5,  198000000,  17.85,  1.38,  17.79, 0.45],
    ['00986',  '兆豐全球AI科技', '股票型',    85.6,  158000000,  16.95,  1.22,  16.89, 0.50],
    ['00987',  '永豐台灣科技龍頭','股票型',   125.8,  212000000,  18.35,  1.15,  18.29, 0.40],
    ['00988',  '統一全球AI領袖', '股票型',    72.3,  135000000,  16.15,  1.08,  16.10, 0.50],
    ['00989',  '台新台灣龍頭',   '股票型',   145.6,  242000000,  18.65,  0.92,  18.59, 0.35],
    ['00990',  '富邦台灣ESG永續','股票型',    98.5,  178000000,  17.25,  0.72,  17.19, 0.45],
    ['00991',  '野村台灣優質50', '股票型',   112.8,  198000000,  17.85,  0.85,  17.79, 0.40],
    ['00992',  '凱基台灣科技龍頭','股票型',   85.4,  158000000,  16.75,  0.95,  16.70, 0.45],
    ['00993',  '群益台灣ESG龍頭','股票型',    95.6,  172000000,  17.15,  0.78,  17.09, 0.45],
    ['00994',  '中信台灣龍頭永續','股票型',  125.8,  212000000,  17.65,  0.82,  17.59, 0.40],
    ['00995',  '兆豐台灣精選',   '股票型',   145.4,  245000000,  18.25,  0.88,  18.19, 0.40],
    ['00996',  '統一台灣藍籌50', '股票型',   168.3,  278000000,  18.75,  0.95,  18.69, 0.35],
    ['00997',  '永豐台灣ESG精選','股票型',    85.2,  158000000,  16.85,  0.72,  16.80, 0.45],
    ['00998',  '台新全球ESG優質','股票型',    65.4,  125000000,  15.95,  0.65,  15.90, 0.50],
    ['00999',  '富邦台灣永續龍頭','股票型',  112.5,  198000000,  17.45,  0.78,  17.39, 0.40],
    ['01000',  '元大全球永續精選','股票型',   95.6,  172000000,  17.05,  0.68,  17.00, 0.45],
  ]

  // compute turnover_rate, portfolio_turnover, and enrich
  const etfs = raw.map(([etf_id, name, etf_type, asset_scale, outstanding_units, close_price, price_change_pct, nav, management_fee]) => {
    // simulate daily volume: 0.1%–5% of outstanding_units (random but deterministic-ish by hash)
    const seed = etf_id.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
    const volRatio = 0.001 + (seed % 97) / 97 * 0.049
    const volume = Math.round(outstanding_units * volRatio)
    const turnover_rate = parseFloat(((volume / outstanding_units) * 100).toFixed(4))
    const premium_discount = parseFloat(((close_price - nav) / nav * 100).toFixed(3))

    // portfolio_turnover (持股週轉率, annual %): estimated by type
    const portfolio_turnover = (() => {
      if (etf_type === '槓桿/反向') return 500 + (seed % 300)       // daily rebalancing
      if (etf_type === '商品型')   return 150 + (seed % 80)        // futures rolling
      if (etf_type === '債券型')   return 25  + (seed % 40)        // bond ladder
      if (etf_id === '0050' || etf_id === '006208') return 5 + (seed % 8)  // pure passive
      return 30 + (seed % 55)                                       // stock ETFs 30–85%
    })()

    let color_tier = 'neutral'
    if (price_change_pct >= 5) color_tier = 'deep_red'
    else if (price_change_pct >= 1) color_tier = 'light_red'
    else if (price_change_pct > -1) color_tier = 'neutral'
    else if (price_change_pct >= -5) color_tier = 'light_green'
    else color_tier = 'deep_green'

    return { etf_id, name, etf_type, asset_scale, outstanding_units, volume, turnover_rate,
             close_price, price_change_pct, nav, premium_discount, management_fee,
             portfolio_turnover, color_tier, turnover_rank: 0, asset_scale_rank: 0 }
  })

  // assign ranks
  const byTurnover = [...etfs].sort((a, b) => b.turnover_rate - a.turnover_rate)
  byTurnover.forEach((e, i) => { e.turnover_rank = i + 1 })
  const byScale = [...etfs].sort((a, b) => b.asset_scale - a.asset_scale)
  byScale.forEach((e, i) => { e.asset_scale_rank = i + 1 })

  return etfs
})()

function _isMockMarketOpen() {
  const now = new Date()
  const day = now.getDay()                        // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return false
  const h = now.getHours(), m = now.getMinutes()
  const mins = h * 60 + m
  return mins >= 9 * 60 && mins <= 13 * 60 + 30  // 09:00–13:30 台北時間
}

function buildMockPayload(sortBy) {
  const sorted = [...MOCK_ETFS].sort((a, b) =>
    sortBy === 'asset_scale'
      ? a.asset_scale_rank - b.asset_scale_rank
      : a.turnover_rank - b.turnover_rank
  )
  return {
    sort_by: sortBy,
    date: new Date().toLocaleDateString('sv-SE'),
    market_open: _isMockMarketOpen(),
    updated_at: new Date().toISOString(),
    etfs: sorted,
  }
}

// ── Composable ──
export function useEtfData() {
  const store = useStockStore()
  let timerId = null
  let inFlightPromise = null
  let abortController = null
  let nextIntervalMs = POLL_INTERVAL_MS
  let pollingEnabled = true

  function clearTimer() {
    if (timerId) { clearTimeout(timerId); timerId = null }
  }

  function scheduleNextPoll() {
    clearTimer()
    if (!pollingEnabled) return
    timerId = setTimeout(fetchData, nextIntervalMs)
  }

  async function fetchData() {
    if (inFlightPromise) return inFlightPromise

    store.setEtfLoading(true)

    const request = (async () => {
      try {
        let data
        if (MOCK_MODE) {
          // Simulate network latency
          await new Promise(r => setTimeout(r, 180))
          data = buildMockPayload(store.etfSortBy)
        } else {
          abortController = new AbortController()
          const res = await fetch(
            `${API_BASE}/api/etf?sort_by=${store.etfSortBy}&limit=100`,
            { signal: abortController.signal }
          )
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          data = await res.json()
        }

        store.setEtfData(data)
        nextIntervalMs = POLL_INTERVAL_MS

        if (!data.market_open) {
          pollingEnabled = false
          clearTimer()
        } else {
          scheduleNextPoll()
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          store.setEtfError(err.message)
          nextIntervalMs = Math.min(nextIntervalMs * 2, MAX_BACKOFF_MS)
          scheduleNextPoll()
        }
      } finally {
        store.setEtfLoading(false)
      }
    })()

    inFlightPromise = request.finally(() => {
      if (inFlightPromise === request) inFlightPromise = null
      abortController = null
    })

    return inFlightPromise
  }

  function startPolling() {
    pollingEnabled = true
    nextIntervalMs = POLL_INTERVAL_MS
    clearTimer()
    fetchData()
  }

  function stopPolling() {
    pollingEnabled = false
    clearTimer()
    if (abortController) { abortController.abort(); abortController = null }
  }

  // Re-fetch immediately when sort mode changes
  watch(() => store.etfSortBy, () => startPolling())

  function onVisibilityChange() {
    if (document.hidden) { stopPolling(); return }
    if (!navigator.onLine) return
    startPolling()
  }

  startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('online', startPolling)
  window.addEventListener('offline', stopPolling)

  onUnmounted(() => {
    stopPolling()
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('online', startPolling)
    window.removeEventListener('offline', stopPolling)
  })

  return { fetchData }
}
