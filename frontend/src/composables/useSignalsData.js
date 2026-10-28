/**
 * useSignalsData.js — nightly 籌碼 / 技術 indicators loader
 *
 * The data changes once per trading day (crawler nightly 03:00), so fetch on
 * mount and re-check every 5 minutes; the backend ETag makes repeats ~free.
 * Failures keep the last good payload (chips simply stay as they were).
 */

import { onUnmounted } from 'vue'
import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const POLL_INTERVAL_MS = 300_000

export function useSignalsData() {
  const store = useStockStore()
  let timerId = null

  async function fetchSignals() {
    try {
      const res = await fetch(`${API_BASE}/api/signals`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      store.setSignals(await res.json())
    } catch (err) {
      console.warn('[useSignalsData] daily signals unavailable:', err.message)
    } finally {
      clearTimeout(timerId)
      timerId = setTimeout(fetchSignals, POLL_INTERVAL_MS)
    }
  }

  fetchSignals()
  onUnmounted(() => clearTimeout(timerId))

  return { fetchSignals }
}
