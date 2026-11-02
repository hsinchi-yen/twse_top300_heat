/**
 * useScoreData.test.js — force refresh: the crawler's long recompute must show
 * progress, survive a stall, and end cleanly. The module keeps poll state between
 * calls, so each test ends by settling it.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { fetchScores, forceRefreshScores } from '../src/composables/useScoreData'
import { useStockStore } from '../src/stores/stockStore'
import ScoreRefreshBtn from '../src/components/ScoreRefreshBtn.vue'

const SECOND = 1000

function respond(body) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
}

function api(body) {
  const fetchMock = vi.fn(() => respond(body))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const running = (done, total = 600, scores = { A: { score: 1, max_score: 24 } }) => ({
  date: 'd', generated_at: 'g', scores, fetching: true, progress: { done, total },
})
const finished = { date: 'd', generated_at: 'g', scores: { A: { score: 2, max_score: 24 } }, fetching: false }

beforeEach(() => {
  vi.useFakeTimers()
  setActivePinia(createPinia())
})

afterEach(async () => {
  api(finished)
  await fetchScores()   // clears any pending poll left by the test
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('forceRefreshScores', () => {
  it('asks the backend to refresh, then polls without force', async () => {
    const fetchMock = api(running(10))
    await forceRefreshScores()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/scores?force=true')
    await vi.advanceTimersByTimeAsync(30 * SECOND)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/scores')
    expect(useStockStore().scoreProgress).toEqual({ done: 10, total: 600 })
  })

  it('shows partial results while fetching', async () => {
    api(running(10))
    await forceRefreshScores()
    const store = useStockStore()
    expect(store.scoresFetching).toBe(true)
    expect(store.scores.A.score).toBe(1)
  })

  it('finishes when the crawler does', async () => {
    const fetchMock = api(running(10))
    await forceRefreshScores()
    fetchMock.mockImplementation(() => respond(finished))
    await vi.advanceTimersByTimeAsync(30 * SECOND)
    const store = useStockStore()
    expect(store.scoresFetching).toBe(false)
    expect(store.scoreProgress).toBe(null)
    expect(store.scores.A.score).toBe(2)
    const calls = fetchMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(5 * 60 * SECOND)
    expect(fetchMock.mock.calls.length).toBe(calls)
  })

  it('flags a stall when the counter stops moving', async () => {
    api(running(10))
    await forceRefreshScores()
    const store = useStockStore()
    await vi.advanceTimersByTimeAsync(4 * 60 * SECOND)
    expect(store.scoresStalled).toBe(false)
    await vi.advanceTimersByTimeAsync(2 * 60 * SECOND)
    expect(store.scoresStalled).toBe(true)
  })

  it('clears the stall when progress resumes', async () => {
    const fetchMock = api(running(10))
    await forceRefreshScores()
    const store = useStockStore()
    await vi.advanceTimersByTimeAsync(6 * 60 * SECOND)
    expect(store.scoresStalled).toBe(true)
    fetchMock.mockImplementation(() => respond(running(50)))
    await vi.advanceTimersByTimeAsync(30 * SECOND)
    expect(store.scoresStalled).toBe(false)
  })

  it('on a cold start falls back to counting scored stocks', async () => {
    const fetchMock = api({ date: '', scores: { A: { score: 1, max_score: 24 } }, fetching: true })
    await forceRefreshScores()
    fetchMock.mockImplementation(() => respond({
      date: '', fetching: true,
      scores: { A: { score: 1, max_score: 24 }, B: { score: 2, max_score: 24 }, C: { score: null } },
    }))
    await vi.advanceTimersByTimeAsync(4 * 60 * SECOND)
    expect(useStockStore().scoresStalled).toBe(false)
  })

  it('a failure mid-refresh stops the spinner and keeps the scores', async () => {
    const fetchMock = api(running(10))
    await forceRefreshScores()
    fetchMock.mockImplementation(() => Promise.resolve({ ok: false, status: 500 }))
    await vi.advanceTimersByTimeAsync(30 * SECOND)
    const store = useStockStore()
    expect(store.scoresFetching).toBe(false)
    expect(store.scores.A.score).toBe(1)
  })
})

describe('ScoreRefreshBtn', () => {
  it('starts a refresh, disables while running, and explains the cost', async () => {
    const fetchMock = api(running(10))
    const w = mount(ScoreRefreshBtn)
    expect(w.attributes('title')).toContain('90 分鐘')
    await w.trigger('click')
    await flushPromises()
    expect(fetchMock.mock.calls[0][0]).toContain('force=true')
    expect(w.attributes('disabled')).toBeDefined()
    expect(w.classes()).toContain('spinning')
  })

  it('a stalled run can be retried', async () => {
    const fetchMock = api(running(10))
    const w = mount(ScoreRefreshBtn)
    await w.trigger('click')
    await flushPromises()
    useStockStore().setScoresStalled(true)
    await w.vm.$nextTick()
    expect(w.attributes('disabled')).toBeUndefined()
    expect(w.attributes('title')).toContain('重試')
    await w.trigger('click')
    await flushPromises()
    expect(fetchMock.mock.calls.filter(c => c[0].includes('force=true'))).toHaveLength(2)
  })
})
