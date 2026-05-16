/**
 * useStockData.js — polling composable
 *
 * Fetches /api/stocks/top100 every 60s while market is open.
 * Stops polling when market_open === false.
 * Immediately re-fetches when mode changes.
 */

import { watch, onUnmounted } from 'vue'
import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const POLL_INTERVAL_MS = 60_000

export function useStockData() {
  const store = useStockStore()
  let timerId = null

  async function fetchData() {
    store.setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/stocks/top100?mode=${store.mode}&limit=300`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      store.setData(data)

      // Stop polling after market closes
      if (!data.market_open) {
        clearInterval(timerId)
        timerId = null
      }
    } catch (err) {
      store.setError(err.message)
    } finally {
      store.setLoading(false)
    }
  }

  function startPolling() {
    clearInterval(timerId)
    fetchData()
    timerId = setInterval(fetchData, POLL_INTERVAL_MS)
  }

  // Re-fetch immediately on mode change
  watch(() => store.mode, () => startPolling())

  // Start on mount
  startPolling()

  onUnmounted(() => clearInterval(timerId))

  return { fetchData }
}
