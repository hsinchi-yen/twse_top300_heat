/**
 * useScoreData.js — buy score loader with progressive background fetch support
 *
 * - Reads finmind_token from localStorage and passes as X-FinMind-Token header
 * - When backend responds with {fetching: true}, polls every 30s to pick up
 *   partial results as they are written (every 50 stocks on the backend)
 * - setPartialScores: shows whatever scores exist while still showing '...' for
 *   stocks not yet fetched; setScores: final state, clears fetching indicator
 * - Stall guard: if fetching stays true but no new scores arrive for STALL_MS,
 *   flag scoresStalled so the UI can re-enable a manual retry (the crawler may
 *   have crashed; the backend stale-flag timeout lets a fresh force succeed)
 */

import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const STORAGE_KEY = 'finmind_token'
const POLL_INTERVAL_MS = 30_000
const STALL_MS = 5 * 60_000  // no progress for 5 min → allow manual retry

export function getStoredToken() {
  return localStorage.getItem(STORAGE_KEY) || ''
}

let _pollTimer = null
let _lastScoredCount = 0
let _lastProgressAt = 0

function _clearPoll() {
  if (_pollTimer !== null) {
    clearTimeout(_pollTimer)
    _pollTimer = null
  }
}

function _buildHeaders(token) {
  return token ? { 'X-FinMind-Token': token } : {}
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

async function _doFetch(url, headers = {}) {
  _clearPoll()
  const store = useStockStore()

  try {
    const res = await fetch(url, { headers })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()

    store.setScoreMeta(data.date, data.generated_at)
    const hasScores = data.scores && Object.keys(data.scores).length > 0

    if (data.fetching) {
      store.setScoresFetching(true)
      if (hasScores) {
        store.setPartialScores(data.scores)
      }

      // Stall detection: track whether the scored count advances between polls.
      const count = _scoredCount(data.scores)
      const now = Date.now()
      if (count > _lastScoredCount) {
        _lastScoredCount = count
        _lastProgressAt = now
        store.setScoresStalled(false)
      } else if (_lastProgressAt && now - _lastProgressAt > STALL_MS) {
        store.setScoresStalled(true)
      }

      // Poll with plain (no force) URL so each subsequent call doesn't re-wipe cache
      const token = getStoredToken()
      _pollTimer = setTimeout(
        () => _doFetch(`${API_BASE}/api/scores`, _buildHeaders(token)),
        POLL_INTERVAL_MS,
      )
      return
    }

    store.setScores(data.scores ?? {})
  } catch (err) {
    console.warn('[useScoreData] buy scores unavailable:', err.message)
    store.setScores({})
  }
}

export async function fetchScores() {
  const token = getStoredToken()
  return _doFetch(`${API_BASE}/api/scores`, _buildHeaders(token))
}

export async function forceRefreshScores() {
  const token = getStoredToken()
  const store = useStockStore()
  store.setScoresFetching(true)
  store.setScoresStalled(false)
  _lastScoredCount = 0
  _lastProgressAt = Date.now()
  return _doFetch(`${API_BASE}/api/scores?force=true`, _buildHeaders(token))
}
