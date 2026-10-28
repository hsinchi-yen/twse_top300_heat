/**
 * watchlistStore.js — 自選股 (backend SQLite via /api/watchlist, shared across devices)
 *
 * pin / unpin / saveNote update state optimistically and roll back when the API
 * call fails, leaving a human-readable `error` (e.g. 409 → 自選股已滿).
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const ERROR_TEXT = {
  404: '最新交易日查無此股票',
  409: '自選股已滿，請先移除再加入',
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const err = new Error(ERROR_TEXT[res.status] ?? `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.status === 204 ? null : res.json()
}

export const useWatchlistStore = defineStore('watchlist', () => {
  const items = ref([])      // [{stock_id, note, added_at, quote}]
  const loaded = ref(false)
  const error = ref(null)

  const pinnedIds = computed(() => new Set(items.value.map(i => i.stock_id)))

  function isPinned(stockId) {
    return pinnedIds.value.has(stockId)
  }

  async function load() {
    try {
      const data = await request('/api/watchlist')
      items.value = data.items ?? []
      loaded.value = true
      error.value = null
    } catch (err) {
      error.value = err.message
    }
  }

  async function pin(stockId) {
    if (isPinned(stockId)) return true
    const placeholder = { stock_id: stockId, note: '', added_at: '', quote: null }
    items.value = [...items.value, placeholder]
    try {
      const saved = await request(`/api/watchlist/${stockId}`, { method: 'PUT' })
      items.value = items.value.map(i => (i.stock_id === stockId ? saved : i))
      error.value = null
      return true
    } catch (err) {
      items.value = items.value.filter(i => i.stock_id !== stockId)
      error.value = err.message
      return false
    }
  }

  async function unpin(stockId) {
    const before = items.value
    items.value = before.filter(i => i.stock_id !== stockId)
    try {
      await request(`/api/watchlist/${stockId}`, { method: 'DELETE' })
      error.value = null
      return true
    } catch (err) {
      items.value = before
      error.value = err.message
      return false
    }
  }

  function toggle(stockId) {
    return isPinned(stockId) ? unpin(stockId) : pin(stockId)
  }

  async function saveNote(stockId, note) {
    try {
      const saved = await request(`/api/watchlist/${stockId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note }),
      })
      items.value = items.value.map(i => (i.stock_id === stockId ? saved : i))
      error.value = null
      return true
    } catch (err) {
      error.value = err.message
      return false
    }
  }

  function clearError() {
    error.value = null
  }

  return { items, loaded, error, pinnedIds, isPinned, load, pin, unpin, toggle, saveNote, clearError }
})
