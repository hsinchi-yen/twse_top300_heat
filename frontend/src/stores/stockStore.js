import { defineStore } from 'pinia'
import { ref } from 'vue'
import { DEFAULT_MOBILE_DENSITY, MOBILE_DENSITY, DEFAULT_TABLET_DENSITY, TABLET_DENSITY } from '../constants'

const DENSITY_KEY        = 'mobile_density'
const TABLET_DENSITY_KEY = 'tablet_density'

export const useStockStore = defineStore('stock', () => {
  // ── grid size (desktop) ──
  const gridSize = ref(6)           // 6 | 5 | 4

  // ── mobile card density ──
  const _storedDensity = (typeof localStorage !== 'undefined' && localStorage.getItem(DENSITY_KEY)) || ''
  const mobileDensity = ref(_storedDensity in MOBILE_DENSITY ? _storedDensity : DEFAULT_MOBILE_DENSITY)

  // ── tablet card density ──
  const _storedTabletDensity = (typeof localStorage !== 'undefined' && localStorage.getItem(TABLET_DENSITY_KEY)) || ''
  const tabletDensity = ref(_storedTabletDensity in TABLET_DENSITY ? _storedTabletDensity : DEFAULT_TABLET_DENSITY)

  // ── stock mode state ──
  const mode = ref('turnover')      // 'volume' | 'turnover' | 'etf' | 'buy_score'
  const sectors = ref([])
  const date = ref('')
  const marketOpen = ref(true)
  const updatedAt = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // ── buy score state ──
  const scores = ref({})          // {stock_id: {score, max_score}}
  const scoresLoaded = ref(false)
  const scoresFetching = ref(false)
  const scoreDate = ref('')        // 評分資料日期 (from /api/scores `date`)
  const scoreGeneratedAt = ref('') // 評分完成時間 (from /api/scores `generated_at`)
  const scoresStalled = ref(false) // background fetch appears stuck → allow manual retry
  const scoreProgress = ref(null)  // {done, total} for the active run, or null
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
    if (typeof localStorage !== 'undefined') localStorage.setItem(DENSITY_KEY, d)
  }

  function setTabletDensity(d) {
    if (!(d in TABLET_DENSITY)) return
    tabletDensity.value = d
    if (typeof localStorage !== 'undefined') localStorage.setItem(TABLET_DENSITY_KEY, d)
  }

  function setMode(newMode) {
    mode.value = newMode
  }

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

  return {
    gridSize, setGridSize,
    mobileDensity, setMobileDensity,
    tabletDensity, setTabletDensity,
    mode, sectors, date, marketOpen, updatedAt, loading, error,
    setMode, setData, setLoading, setError,
    etfs, etfDate, etfUpdatedAt, etfLoading, etfError, etfSortBy,
    setEtfData, setEtfLoading, setEtfError, setEtfSortBy,
    scores, scoresLoaded, scoresFetching, scoreDate, scoreGeneratedAt, scoresStalled, scoreProgress,
    setScores, setPartialScores, setScoresFetching, setScoreMeta, setScoresStalled, setScoreProgress,
  }
})
