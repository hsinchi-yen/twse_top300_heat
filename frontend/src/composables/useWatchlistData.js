/**
 * useWatchlistData.js — 自選股 loader
 *
 * Loads once on mount (so ☆/★ are correct in every view), reloads on entering
 * watchlist mode (picks up pins made on another device), and polls only while
 * watchlist mode is active: 60s 盤中 / 5min 盤後, same cadence as stocks.
 */

import { watch, onUnmounted } from 'vue'
import { useStockStore } from '../stores/stockStore'
import { useWatchlistStore } from '../stores/watchlistStore'

const POLL_INTERVAL_MS = 60_000
const CLOSED_CHECK_INTERVAL_MS = 300_000

export function useWatchlistData() {
  const stock = useStockStore()
  const wl = useWatchlistStore()
  let timerId = null

  function clearTimer() {
    if (timerId) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  async function tick() {
    clearTimer()
    await wl.load()
    if (stock.mode !== 'watchlist' || document.hidden) return
    timerId = setTimeout(tick, stock.marketOpen ? POLL_INTERVAL_MS : CLOSED_CHECK_INTERVAL_MS)
  }

  watch(() => stock.mode, (mode) => {
    if (mode === 'watchlist') tick()
    else clearTimer()
  })

  function onVisibilityChange() {
    if (document.hidden) clearTimer()
    else if (stock.mode === 'watchlist') tick()
  }

  tick()
  document.addEventListener('visibilitychange', onVisibilityChange)

  onUnmounted(() => {
    clearTimer()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return { reload: tick }
}
