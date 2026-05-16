import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useStockStore = defineStore('stock', () => {
  // ── grid size ──
  const gridSize = ref(6)           // 6 | 5 | 4

  // ── stock mode state ──
  const mode = ref('turnover')      // 'volume' | 'turnover' | 'etf'
  const sectors = ref([])
  const date = ref('')
  const marketOpen = ref(true)
  const updatedAt = ref(null)
  const loading = ref(false)
  const error = ref(null)

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

  return {
    gridSize, setGridSize,
    mode, sectors, date, marketOpen, updatedAt, loading, error,
    setMode, setData, setLoading, setError,
    etfs, etfDate, etfUpdatedAt, etfLoading, etfError, etfSortBy,
    setEtfData, setEtfLoading, setEtfError, setEtfSortBy,
  }
})
