/**
 * polling.test.js — the 365×24 contract: after the first load the dashboard must
 * keep refreshing. Regression: the single-flight guard was never released, so
 * every poll after the first was a silent no-op.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, nextTick } from 'vue'
import { useStockData } from '../src/composables/useStockData'
import { useEtfData } from '../src/composables/useEtfData'
import { useScorePolling } from '../src/composables/useScoreData'
import { useStockStore } from '../src/stores/stockStore'

const MINUTE = 60_000

function harness(useComposable) {
  return mount(defineComponent({
    setup() {
      useComposable()
      return () => h('div')
    },
  }))
}

function api(marketOpen) {
  const fetchMock = vi.fn(() => Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ sectors: [], etfs: [], market_open: marketOpen, date: 'd' }),
  }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function advance(ms) {
  await vi.advanceTimersByTimeAsync(ms)
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers()
  setActivePinia(createPinia())
  localStorage.clear()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('useStockData polling', () => {
  it('keeps fetching every minute while the market is open', async () => {
    const fetchMock = api(true)
    const w = harness(useStockData)
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await advance(MINUTE)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    await advance(MINUTE)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    w.unmount()
  })

  it('slows to five minutes after the close', async () => {
    const fetchMock = api(false)
    const w = harness(useStockData)
    await flushPromises()
    await advance(4 * MINUTE)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await advance(MINUTE)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('refetches when the view changes', async () => {
    const fetchMock = api(true)
    const w = harness(useStockData)
    await flushPromises()
    useStockStore().setMode('volume')
    await nextTick()
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('recovers after a failed request', async () => {
    const fetchMock = api(true)
    fetchMock.mockImplementationOnce(() => Promise.reject(new Error('down')))
    const w = harness(useStockData)
    await flushPromises()
    expect(useStockStore().error).toBe('down')
    await advance(2 * MINUTE)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(useStockStore().error).toBe(null)
    w.unmount()
  })

  it('overlapping triggers share one request', async () => {
    let release
    const fetchMock = vi.fn(() => new Promise((resolve) => {
      release = () => resolve({ ok: true, status: 200, json: () => Promise.resolve({ sectors: [], market_open: true }) })
    }))
    vi.stubGlobal('fetch', fetchMock)
    const w = harness(useStockData)
    useStockStore().setMode('volume')
    await nextTick()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    release()
    await flushPromises()
    w.unmount()
  })
})

describe('useScorePolling', () => {
  const scoresApi = (scores, fetching = false) => vi.fn(() => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve({ date: 'd', generated_at: 'g', scores, fetching }),
  }))

  it('picks up the nightly scores without a page reload', async () => {
    const fetchMock = scoresApi({ A: { score: 1 } })
    vi.stubGlobal('fetch', fetchMock)
    const w = harness(useScorePolling)
    await flushPromises()
    expect(useStockStore().scores.A.score).toBe(1)
    fetchMock.mockImplementation(scoresApi({ A: { score: 2 } }))
    await advance(5 * MINUTE)
    expect(useStockStore().scores.A.score).toBe(2)
    w.unmount()
  })

  it('a failed re-check keeps the last good scores', async () => {
    const fetchMock = scoresApi({ A: { score: 1 } })
    vi.stubGlobal('fetch', fetchMock)
    const w = harness(useScorePolling)
    await flushPromises()
    fetchMock.mockImplementation(() => Promise.reject(new Error('down')))
    await advance(5 * MINUTE)
    expect(useStockStore().scores.A.score).toBe(1)
    w.unmount()
  })

  it('a first load that fails still ends the loading state', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('down'))))
    const w = harness(useScorePolling)
    await flushPromises()
    expect(useStockStore().scoresLoaded).toBe(true)
    w.unmount()
  })

  it('stops when the app unmounts', async () => {
    const fetchMock = scoresApi({})
    vi.stubGlobal('fetch', fetchMock)
    const w = harness(useScorePolling)
    await flushPromises()
    w.unmount()
    const before = fetchMock.mock.calls.length
    await advance(15 * MINUTE)
    expect(fetchMock.mock.calls.length).toBe(before)
  })
})

describe('useEtfData polling', () => {
  it('keeps fetching every minute while the market is open', async () => {
    const fetchMock = api(true)
    const w = harness(useEtfData)
    await flushPromises()
    await advance(MINUTE)
    await advance(MINUTE)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    w.unmount()
  })

  it('refetches when the sort changes', async () => {
    const fetchMock = api(true)
    const w = harness(useEtfData)
    await flushPromises()
    useStockStore().setEtfSortBy('asset_scale')
    await nextTick()
    await flushPromises()
    expect(fetchMock.mock.calls[1][0]).toContain('sort_by=asset_scale')
    w.unmount()
  })
})
