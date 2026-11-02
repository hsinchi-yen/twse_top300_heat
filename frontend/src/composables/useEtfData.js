/**
 * useEtfData.js — ETF data polling composable
 *
 * Polls /api/etf.
 *
 * Polling logic mirrors useStockData: 60s interval, stops after market close,
 * re-fetches immediately when etfSortBy changes.
 */

import { watch, onUnmounted } from 'vue'
import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const POLL_INTERVAL_MS = 60_000          // 盤中：每 60 秒
const CLOSED_CHECK_INTERVAL_MS = 60_000  // 盤前/盤後：同 60 秒輕量 check（ETag 304 不耗資源）
const MAX_BACKOFF_MS = 300_000
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
        abortController = new AbortController()
        const res = await fetch(
          `${API_BASE}/api/etf?sort_by=${store.etfSortBy}&limit=300`,
          { signal: abortController.signal }
        )
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()

        store.setEtfData(data)

        if (data.market_open) {
          // 盤中：恢復 60 秒標準輪詢
          nextIntervalMs = POLL_INTERVAL_MS
        } else {
          // 盤前/收盤/假日：改用慢速 check，讓 Kiosk 能在 09:00 自動恢復
          // ETag 使 304 Not Modified 幾乎無流量
          nextIntervalMs = CLOSED_CHECK_INTERVAL_MS
        }
        scheduleNextPoll()
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

    // Same guard as useStockData: release on the tracked promise, not `request`.
    const tracked = request.finally(() => {
      if (inFlightPromise === tracked) inFlightPromise = null
      abortController = null
    })
    inFlightPromise = tracked

    return tracked
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
