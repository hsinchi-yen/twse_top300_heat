import { defineStore } from 'pinia'
import { ref } from 'vue'
import { DEFAULT_MOBILE_DENSITY, MOBILE_DENSITY } from '../constants'

const DENSITY_KEY = 'mobile_density'

export const useStockStore = defineStore('stock', () => {
  // ── grid size (desktop) ──
  const gridSize = ref(6)           // 6 | 5 | 4

  // ── mobile card density ──
  const _storedDensity = (typeof localStorage !== 'undefined' && localStorage.getItem(DENSITY_KEY)) || ''
  const mobileDensity = ref(_storedDensity in MOBILE_DENSITY ? _storedDensity : DEFAULT_MOBILE_DENSITY)

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
  }

  // Partial update during background fetch — shows what we have, keeps fetching indicator
  function setPartialScores(payload) {
    scores.value = payload
    scoresLoaded.value = true
  }

  function setScoresFetching(val) {
    scoresFetching.value = val
  }

  return {
    gridSize, setGridSize,
    mobileDensity, setMobileDensity,
    mode, sectors, date, marketOpen, updatedAt, loading, error,
    setMode, setData, setLoading, setError,
    etfs, etfDate, etfUpdatedAt, etfLoading, etfError, etfSortBy,
    setEtfData, setEtfLoading, setEtfError, setEtfSortBy,
    scores, scoresLoaded, scoresFetching, setScores, setPartialScores, setScoresFetching,
  }
})
