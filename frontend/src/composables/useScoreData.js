/**
 * useScoreData.js — buy score loader with progressive background fetch support
 *
 * - When backend responds with {fetching: true}, polls every 30s to pick up
 *   partial results as they are written (every 50 stocks on the backend)
 * - setPartialScores: shows whatever scores exist while still showing '...' for
 *   stocks not yet fetched; setScores: final state, clears fetching indicator
 * - Stall guard: if fetching stays true but no new scores arrive for STALL_MS,
 *   flag scoresStalled so the UI can re-enable a manual retry (the crawler may
 *   have crashed; the backend stale-flag timeout lets a fresh force succeed)
 */

import { onUnmounted } from 'vue'
import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const POLL_INTERVAL_MS = 30_000
const STALL_MS = 5 * 60_000  // no progress for 5 min → allow manual retry
const RECHECK_MS = 300_000   // scores change nightly; a long-lived tab must still pick them up

let _pollTimer = null
let _lastScoredCount = 0
let _lastProgressAt = 0

function _clearPoll() {
  if (_pollTimer !== null) {
    clearTimeout(_pollTimer)
    _pollTimer = null
  }
}

function _scoredCount(scores) {
  if (!scores) return 0
  let n = 0
  for (const k in scores) {
    const s = scores[k]
    if (s && s.score != null && s.max_score !== 0) n++
  }
  return n
}

async function _doFetch(url) {
  _clearPoll()
  const store = useStockStore()

  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()

    store.setScoreMeta(data.date, data.generated_at)
    const hasScores = data.scores && Object.keys(data.scores).length > 0

    if (data.fetching) {
      store.setScoresFetching(true)
      store.setScoreProgress(data.progress ?? null)
      if (hasScores) {
        store.setPartialScores(data.scores)
      }

      // Stall detection: prefer the crawler's real recompute counter (data.progress),
      // which advances during a force refresh even though the merged baseline stays
      // full; fall back to counting scored stocks for a cold start.
      const count = data.progress ? data.progress.done : _scoredCount(data.scores)
      const now = Date.now()
      if (count > _lastScoredCount) {
        _lastScoredCount = count
        _lastProgressAt = now
        store.setScoresStalled(false)
      } else if (_lastProgressAt && now - _lastProgressAt > STALL_MS) {
        store.setScoresStalled(true)
      }

      // Poll with plain (no force) URL so each subsequent call doesn't re-wipe cache
      _pollTimer = setTimeout(() => _doFetch(`${API_BASE}/api/scores`), POLL_INTERVAL_MS)
      return
    }

    store.setScores(data.scores ?? {})
  } catch (err) {
    console.warn('[useScoreData] buy scores unavailable:', err.message)
    // One failed request must not blank the risk flags on a screen that had them.
    if (store.scoresLoaded) store.setScoresFetching(false)
    else store.setScores({})
  }
}

export async function fetchScores() {
  return _doFetch(`${API_BASE}/api/scores`)
}

/** Loads scores and re-checks for as long as the app runs (kiosks never reload). */
export function useScorePolling() {
  const store = useStockStore()
  fetchScores()
  const timer = setInterval(() => {
    if (!document.hidden && !store.scoresFetching) fetchScores()
  }, RECHECK_MS)
  onUnmounted(() => {
    clearInterval(timer)
    _clearPoll()
  })
}

export async function forceRefreshScores() {
  const store = useStockStore()
  store.setScoresFetching(true)
  store.setScoresStalled(false)
  _lastScoredCount = 0
  _lastProgressAt = Date.now()
  return _doFetch(`${API_BASE}/api/scores?force=true`)
}
