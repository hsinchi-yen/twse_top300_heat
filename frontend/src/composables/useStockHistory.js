/**
 * useStockHistory.js — price / flow history and score trend for the open stock.
 *
 * Quick switches between stocks can resolve out of order; only the latest
 * request may write. The two sources fail independently, so a missing score
 * history never hides the price chart.
 */

import { ref, watch } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function useStockHistory(stockId) {
  const bars = ref([])
  const flows = ref([])
  const scorePoints = ref([])
  const loading = ref(false)
  const failed = ref(false)
  let latest = 0

  async function load(id) {
    const request = ++latest
    bars.value = []
    flows.value = []
    scorePoints.value = []
    failed.value = false
    if (!id) {
      loading.value = false
      return
    }
    loading.value = true
    const [history, scores] = await Promise.allSettled([
      getJson(`/api/stocks/${encodeURIComponent(id)}/history`),
      getJson(`/api/scores/${encodeURIComponent(id)}/history`),
    ])
    if (request !== latest) return
    if (history.status === 'fulfilled') {
      bars.value = history.value.bars ?? []
      flows.value = history.value.flows ?? []
    } else {
      failed.value = true
      console.warn('[useStockHistory] history unavailable:', history.reason?.message)
    }
    if (scores.status === 'fulfilled') scorePoints.value = scores.value.points ?? []
    loading.value = false
  }

  watch(stockId, load, { immediate: true })

  return { bars, flows, scorePoints, loading, failed }
}
