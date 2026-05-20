/**
 * useScoreData.js — buy score loader with progressive background fetch support
 *
 * - Reads finmind_token from localStorage and passes as X-FinMind-Token header
 * - When backend responds with {fetching: true}, polls every 30s to pick up
 *   partial results as they are written (every 50 stocks on the backend)
 * - setPartialScores: shows whatever scores exist while still showing '...' for
 *   stocks not yet fetched; setScores: final state, clears fetching indicator
 */

import { useStockStore } from '../stores/stockStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const STORAGE_KEY = 'finmind_token'
const POLL_INTERVAL_MS = 30_000

export function getStoredToken() {
  return localStorage.getItem(STORAGE_KEY) || ''
}

let _pollTimer = null

function _clearPoll() {
  if (_pollTimer !== null) {
    clearTimeout(_pollTimer)
    _pollTimer = null
  }
}

function _buildHeaders(token) {
  return token ? { 'X-FinMind-Token': token } : {}
}

async function _doFetch(url, headers = {}) {
  _clearPoll()
  const store = useStockStore()

  try {
    const res = await fetch(url, { headers })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()

    const hasScores = data.scores && Object.keys(data.scores).length > 0

    if (data.fetching) {
      store.setScoresFetching(true)
      if (hasScores) {
        store.setPartialScores(data.scores)
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
  if (!token) return
  const store = useStockStore()
  store.setScoresFetching(true)
  return _doFetch(`${API_BASE}/api/scores?force=true`, _buildHeaders(token))
}
