/**
 * useStockData.js — polling composable
 *
 * Fetches /api/stocks/top100 every 60s while market is open.
 * When market_open === false (pre-market / after close / weekend),
 * switches to a slow 5-minute check so Kiosk auto-resumes at 09:00.
 * Immediately re-fetches when mode changes.
 */

import { watch, onUnmounted } from 'vue'
import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const POLL_INTERVAL_MS = 60_000          // 盤中：每 60 秒
const CLOSED_CHECK_INTERVAL_MS = 300_000 // 盤前/盤後：每 5 分鐘輕量 check（降低 eMMC 寫入頻率）
const MAX_BACKOFF_MS = 300_000

export function useStockData() {
  const store = useStockStore()
  let timerId = null
  let inFlightPromise = null
  let abortController = null
  let nextIntervalMs = POLL_INTERVAL_MS
  let pollingEnabled = true

  function clearTimer() {
    if (timerId) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  function scheduleNextPoll() {
    clearTimer()
    if (!pollingEnabled) return
    timerId = setTimeout(() => {
      fetchData()
    }, nextIntervalMs)
  }

  async function fetchData() {
    // Single-flight: reuse current request when polling/mode switch overlap.
    if (inFlightPromise) return inFlightPromise

    abortController = new AbortController()
    store.setLoading(true)

    const request = (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/stocks/top100?mode=volume&limit=360`,
          { signal: abortController.signal }
        )
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        store.setData(data)

        if (data.market_open) {
          // 盤中：恢復 60 秒標準輪詢
          nextIntervalMs = POLL_INTERVAL_MS
          scheduleNextPoll()
        } else {
          // 盤前 / 收盤 / 假日：改用慢速 check，讓 Kiosk 能在 09:00 自動恢復
          // ETag 使 304 Not Modified 幾乎無流量
          nextIntervalMs = CLOSED_CHECK_INTERVAL_MS
          scheduleNextPoll()
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          store.setError(err.message)
          nextIntervalMs = Math.min(nextIntervalMs * 2, MAX_BACKOFF_MS)
          scheduleNextPoll()
        }
      } finally {
        store.setLoading(false)
      }
    })()

    inFlightPromise = request.finally(() => {
      if (inFlightPromise === request) {
        inFlightPromise = null
      }
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
  }

  // Re-fetch immediately on stock mode change; ETF mode is handled by useEtfData
  watch(() => store.mode, (newMode) => {
    if (newMode !== 'etf') startPolling()
  })

  function onVisibilityChange() {
    if (document.hidden) {
      stopPolling()
      return
    }
    if (!navigator.onLine) {
      return
    }
    startPolling()
  }

  function onOnline() {
    startPolling()
  }

  function onOffline() {
    stopPolling()
  }

  // Start on mount
  startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)

  onUnmounted(() => {
    stopPolling()
    document.removeEventListener('visibilitychange', onVisibilityChange)
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    if (abortController) {
      abortController.abort()
    }
  })

  return { fetchData }
}
