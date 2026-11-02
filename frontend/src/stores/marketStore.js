/**
 * marketStore.js — /api/market/trend and /api/market/backtest.
 *
 * Both change once per trading day, so failures keep the last good payload and
 * `loaded` lets the view tell "not computed yet" from "still loading".
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const useMarketStore = defineStore('market', () => {
  const trend = ref(null)
  const trendLoaded = ref(false)
  const backtest = ref(null)
  const backtestFailed = ref(false)
  const horizon = ref(20)

  async function loadTrend() {
    try {
      trend.value = await getJson('/api/market/trend')
    } catch (err) {
      console.warn('[marketStore] trend unavailable:', err.message)
    } finally {
      trendLoaded.value = true
    }
  }

  async function loadBacktest(nextHorizon = horizon.value) {
    horizon.value = nextHorizon
    backtestFailed.value = false
    try {
      const data = await getJson(`/api/market/backtest?horizon=${nextHorizon}`)
      // A slower response for a horizon the user already left must not win.
      if (horizon.value === nextHorizon) backtest.value = data
    } catch (err) {
      console.warn('[marketStore] backtest unavailable:', err.message)
      if (horizon.value === nextHorizon) backtestFailed.value = true
    }
  }

  return { trend, trendLoaded, backtest, backtestFailed, horizon, loadTrend, loadBacktest }
})
