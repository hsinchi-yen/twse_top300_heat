/**
 * useScoreData.js — one-shot buy score loader
 *
 * Fetches /api/scores once on mount. Scores are computed once per trading day
 * by the crawler's score_job (16:05) and served from a static JSON cache.
 * Non-fatal: if the endpoint fails, scores simply remain empty.
 */

import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export async function fetchScores() {
  const store = useStockStore()
  try {
    const res = await fetch(`${API_BASE}/api/scores`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    store.setScores(data.scores ?? {})
  } catch (err) {
    console.warn('[useScoreData] buy scores unavailable:', err.message)
    store.setScores({})
  }
}
