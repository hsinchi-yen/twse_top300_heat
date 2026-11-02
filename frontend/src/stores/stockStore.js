import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { DEFAULT_MOBILE_DENSITY, MOBILE_DENSITY, DEFAULT_TABLET_DENSITY, TABLET_DENSITY } from '../constants'

const DENSITY_KEY        = 'mobile_density'
const TABLET_DENSITY_KEY = 'tablet_density'
const MODE_KEY           = 'view_mode'
const HEATMAP_MODE_KEY   = 'heatmap_mode'

export const HEATMAP_MODES = ['volume', 'turnover', 'buy_score']
const MODES = ['overview', ...HEATMAP_MODES, 'etf', 'watchlist']

// Per-viewer convenience: storage can be blocked, so reads and writes never throw.
function readStored(key, allowed, fallback) {
  try {
    const value = localStorage.getItem(key)
    return allowed.includes(value) ? value : fallback
  } catch {
    return fallback
  }
}

function writeStored(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage unavailable — the choice still applies for this session
  }
}

export const useStockStore = defineStore('stock', () => {
  // ── grid size (desktop) ──
  const gridSize = ref(5)           // 6 | 5 | 4（預設 5×5）

  // ── mobile card density ──
  const mobileDensity = ref(readStored(DENSITY_KEY, Object.keys(MOBILE_DENSITY), DEFAULT_MOBILE_DENSITY))

  // ── tablet card density ──
  const tabletDensity = ref(readStored(TABLET_DENSITY_KEY, Object.keys(TABLET_DENSITY), DEFAULT_TABLET_DENSITY))

  // ── stock mode state ──
  const mode = ref(readStored(MODE_KEY, MODES, 'overview'))
  const heatmapMode = ref(readStored(HEATMAP_MODE_KEY, HEATMAP_MODES, 'turnover'))
  const sectors = ref([])
  const date = ref('')
  const marketOpen = ref(true)
  const updatedAt = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // ── buy score state ──
  const scores = ref({})          // {stock_id: {score, max_score, fundamentals_uptrend}}
  const scoresLoaded = ref(false)
  const scoresFetching = ref(false)
  const scoreDate = ref('')        // 評分資料日期 (from /api/scores `date`)
  const scoreGeneratedAt = ref('') // 評分完成時間 (from /api/scores `generated_at`)
  const scoresStalled = ref(false) // background fetch appears stuck → allow manual retry
  const scoreProgress = ref(null)  // {done, total} for the active run, or null
  // ── daily signals (GET /api/signals, nightly 03:00 after trading days) ──
  const signals = ref({})          // {stock_id: {inst_streak, above_ma20, vol_ratio, ...}}
  const signalsDate = ref('')
  // ── ETF state ──
  const etfs = ref([])
  const etfDate = ref('')
  const etfUpdatedAt = ref(null)
  const etfLoading = ref(false)
  const etfError = ref(null)
  const etfSortBy = ref('turnover')   // 'turnover' | 'asset_scale'

  function setGridSize(n) {
    gridSize.value = n
  }

  function setMobileDensity(d) {
    if (!(d in MOBILE_DENSITY)) return
    mobileDensity.value = d
    writeStored(DENSITY_KEY, d)
  }

  function setTabletDensity(d) {
    if (!(d in TABLET_DENSITY)) return
    tabletDensity.value = d
    writeStored(TABLET_DENSITY_KEY, d)
  }

  function setMode(newMode) {
    mode.value = newMode
    writeStored(MODE_KEY, newMode)
    if (HEATMAP_MODES.includes(newMode)) {
      heatmapMode.value = newMode
      writeStored(HEATMAP_MODE_KEY, newMode)
    }
  }

  // The display pool: one flat list, shared by every view (CLAUDE.md rules 3/4).
  const stockPool = computed(() => {
    const flat = []
    for (const sector of sectors.value) {
      for (const stock of sector.stocks ?? []) {
        flat.push({ ...stock, sector: sector.name })
      }
    }
    return flat
  })

  function setData(payload) {
    sectors.value = payload.sectors ?? []
    date.value = payload.date ?? ''
    marketOpen.value = payload.market_open ?? false
    updatedAt.value = payload.updated_at ?? null
    error.value = null
  }

  function setLoading(val) {
    loading.value = val
  }

  function setError(msg) {
    error.value = msg
  }

  function setEtfData(payload) {
    etfs.value = payload.etfs ?? []
    etfDate.value = payload.date ?? ''
    etfUpdatedAt.value = payload.updated_at ?? null
    etfError.value = null
    // marketOpen is intentionally NOT synced here —
    // it is authoritative only from setData (real stock API).
  }

  function setEtfLoading(val) {
    etfLoading.value = val
  }

  function setEtfError(msg) {
    etfError.value = msg
  }

  function setEtfSortBy(val) {
    etfSortBy.value = val
  }

  function setScores(payload) {
    scores.value = payload
    scoresLoaded.value = true
    scoresFetching.value = false
    scoresStalled.value = false
    scoreProgress.value = null
  }

  // Partial update during background fetch — shows what we have, keeps fetching indicator
  function setPartialScores(payload) {
    scores.value = payload
    scoresLoaded.value = true
  }

  function setScoresFetching(val) {
    scoresFetching.value = val
  }

  // 評分資料的日期與完成時間（來自 /api/scores 的 date / generated_at）
  function setScoreMeta(date, generatedAt) {
    scoreDate.value = date ?? ''
    scoreGeneratedAt.value = generatedAt ?? ''
  }

  function setScoresStalled(val) {
    scoresStalled.value = val
  }

  // 當前重算進度 {done, total}（force refresh 時保留 baseline，無法從 scores 推算）
  function setScoreProgress(val) {
    scoreProgress.value = val ?? null
  }

  // Skip identical payloads (5-min re-checks): replacing the object would
  // recompute the filtered grid and reset its page for no reason.
  let signalsGeneratedAt = null
  function setSignals(payload) {
    const generatedAt = payload?.generated_at ?? ''
    if (generatedAt && generatedAt === signalsGeneratedAt) return
    signalsGeneratedAt = generatedAt
    signals.value = payload?.signals ?? {}
    signalsDate.value = payload?.date ?? ''
  }

  return {
    gridSize, setGridSize,
    mobileDensity, setMobileDensity,
    tabletDensity, setTabletDensity,
    mode, heatmapMode, sectors, stockPool, date, marketOpen, updatedAt, loading, error,
    setMode, setData, setLoading, setError,
    etfs, etfDate, etfUpdatedAt, etfLoading, etfError, etfSortBy,
    setEtfData, setEtfLoading, setEtfError, setEtfSortBy,
    scores, scoresLoaded, scoresFetching, scoreDate, scoreGeneratedAt, scoresStalled, scoreProgress,
    setScores, setPartialScores, setScoresFetching, setScoreMeta, setScoresStalled, setScoreProgress,
    signals, signalsDate, setSignals,
  }
})
