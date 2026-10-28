/**
 * watchlistStore.test.js — 自選股 store: load / pin / unpin / note with
 * optimistic updates that roll back on API failure.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useWatchlistStore } from '../src/stores/watchlistStore'

const quote = (id) => ({ stock_id: id, name: `股${id}`, rank: 1, close_price: 100, sector: '半導體' })
const item = (id, note = '') => ({ stock_id: id, note, added_at: '2026-10-26T09:00:00+08:00', quote: quote(id) })

function jsonResponse(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })
}

let fetchMock

beforeEach(() => {
  setActivePinia(createPinia())
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

describe('watchlistStore — load', () => {
  it('stores items and marks loaded', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ items: [item('2330')] }))
    const store = useWatchlistStore()
    await store.load()
    expect(store.items.map(i => i.stock_id)).toEqual(['2330'])
    expect(store.loaded).toBe(true)
    expect(store.isPinned('2330')).toBe(true)
    expect(store.isPinned('2317')).toBe(false)
  })

  it('keeps previous items and sets error on failure', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ items: [item('2330')] }))
    const store = useWatchlistStore()
    await store.load()
    fetchMock.mockReturnValueOnce(jsonResponse({}, 500))
    await store.load()
    expect(store.items).toHaveLength(1)
    expect(store.error).toBeTruthy()
  })
})

describe('watchlistStore — pin', () => {
  it('PUTs and replaces the optimistic item with the server item', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse(item('2330')))
    const store = useWatchlistStore()
    const ok = await store.pin('2330')
    expect(ok).toBe(true)
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/watchlist/2330')
    expect(opts.method).toBe('PUT')
    expect(store.items[0].quote.name).toBe('股2330')
  })

  it('is pinned immediately (optimistic) before the request resolves', () => {
    fetchMock.mockReturnValueOnce(new Promise(() => {}))
    const store = useWatchlistStore()
    store.pin('2330')
    expect(store.isPinned('2330')).toBe(true)
  })

  it('rolls back and explains a full watchlist (409)', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ detail: 'full' }, 409))
    const store = useWatchlistStore()
    const ok = await store.pin('2330')
    expect(ok).toBe(false)
    expect(store.isPinned('2330')).toBe(false)
    expect(store.error).toContain('已滿')
  })

  it('rolls back on 404 (not on latest trading date)', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ detail: 'nf' }, 404))
    const store = useWatchlistStore()
    await store.pin('9999')
    expect(store.isPinned('9999')).toBe(false)
    expect(store.error).toBeTruthy()
  })
})

describe('watchlistStore — unpin', () => {
  it('removes optimistically and DELETEs', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ items: [item('2330')] }))
    const store = useWatchlistStore()
    await store.load()
    fetchMock.mockReturnValueOnce(Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve(null) }))
    await store.unpin('2330')
    expect(store.isPinned('2330')).toBe(false)
    expect(fetchMock.mock.calls[1][1].method).toBe('DELETE')
  })

  it('restores the item when DELETE fails', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ items: [item('2330')] }))
    const store = useWatchlistStore()
    await store.load()
    fetchMock.mockReturnValueOnce(Promise.reject(new Error('offline')))
    await store.unpin('2330')
    expect(store.isPinned('2330')).toBe(true)
    expect(store.error).toBeTruthy()
  })

  it('toggle pins and unpins', async () => {
    fetchMock.mockReturnValue(jsonResponse(item('2330')))
    const store = useWatchlistStore()
    await store.toggle('2330')
    expect(store.isPinned('2330')).toBe(true)
    fetchMock.mockReturnValue(Promise.resolve({ ok: true, status: 204, json: () => Promise.resolve(null) }))
    await store.toggle('2330')
    expect(store.isPinned('2330')).toBe(false)
  })
})

describe('watchlistStore — note', () => {
  it('PUTs the note and updates the item', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ items: [item('2330')] }))
    const store = useWatchlistStore()
    await store.load()
    fetchMock.mockReturnValueOnce(jsonResponse(item('2330', '等回測月線')))
    await store.saveNote('2330', '等回測月線')
    const [, opts] = fetchMock.mock.calls[1]
    expect(JSON.parse(opts.body)).toEqual({ note: '等回測月線' })
    expect(store.items[0].note).toBe('等回測月線')
  })
})
