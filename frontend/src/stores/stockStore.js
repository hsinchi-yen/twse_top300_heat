import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useStockStore = defineStore('stock', () => {
  const mode = ref('volume')       // 'volume' | 'turnover'
  const sectors = ref([])
  const date = ref('')
  const marketOpen = ref(true)
  const updatedAt = ref(null)
  const loading = ref(false)
  const error = ref(null)

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

  return { mode, sectors, date, marketOpen, updatedAt, loading, error,
           setMode, setData, setLoading, setError }
})
