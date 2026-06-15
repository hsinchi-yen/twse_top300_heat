import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useStockStore } from '../src/stores/stockStore'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})

describe('stockStore — mobileDensity', () => {
  it('defaults to 2x3', () => {
    const store = useStockStore()
    expect(store.mobileDensity).toBe('2x3')
  })

  it('setMobileDensity updates state', () => {
    const store = useStockStore()
    store.setMobileDensity('2x2')
    expect(store.mobileDensity).toBe('2x2')
  })

  it('setMobileDensity persists to localStorage', () => {
    const store = useStockStore()
    store.setMobileDensity('2x2')
    expect(localStorage.getItem('mobile_density')).toBe('2x2')
  })

  it('accepts 3x3 density', () => {
    const store = useStockStore()
    store.setMobileDensity('3x3')
    expect(store.mobileDensity).toBe('3x3')
  })

  it('ignores unknown density values', () => {
    const store = useStockStore()
    store.setMobileDensity('4x4')
    expect(store.mobileDensity).toBe('2x3')
  })
})

describe('stockStore — buy score state', () => {
  it('scores starts empty', () => {
    const store = useStockStore()
    expect(store.scores).toEqual({})
    expect(store.scoresLoaded).toBe(false)
    expect(store.scoresFetching).toBe(false)
  })

  it('setScores marks loaded and clears fetching', () => {
    const store = useStockStore()
    store.setScoresFetching(true)
    store.setScores({ '2330': { score: 18, max_score: 24 } })
    expect(store.scoresLoaded).toBe(true)
    expect(store.scoresFetching).toBe(false)
    expect(store.scores['2330'].score).toBe(18)
  })

  it('setPartialScores marks loaded but keeps fetching as-is', () => {
    const store = useStockStore()
    store.setScoresFetching(true)
    store.setPartialScores({ '2317': { score: 10, max_score: 24 } })
    expect(store.scoresLoaded).toBe(true)
    expect(store.scoresFetching).toBe(true)
  })

  it('setScoreMeta stores date and generated_at', () => {
    const store = useStockStore()
    store.setScoreMeta('2026-06-01', '2026-06-01T03:42:18+08:00')
    expect(store.scoreDate).toBe('2026-06-01')
    expect(store.scoreGeneratedAt).toBe('2026-06-01T03:42:18+08:00')
  })

  it('setScoresStalled toggles the stalled flag', () => {
    const store = useStockStore()
    expect(store.scoresStalled).toBe(false)
    store.setScoresStalled(true)
    expect(store.scoresStalled).toBe(true)
  })

  it('setScores clears the stalled flag', () => {
    const store = useStockStore()
    store.setScoresStalled(true)
    store.setScores({ '2330': { score: 18, max_score: 24 } })
    expect(store.scoresStalled).toBe(false)
  })

  it('setScoreProgress stores and clears the progress counter', () => {
    const store = useStockStore()
    store.setScoreProgress({ done: 50, total: 600 })
    expect(store.scoreProgress).toEqual({ done: 50, total: 600 })
    store.setScoreProgress(null)
    expect(store.scoreProgress).toBe(null)
  })

  it('setScores clears the progress counter', () => {
    const store = useStockStore()
    store.setScoreProgress({ done: 50, total: 600 })
    store.setScores({ '2330': { score: 18, max_score: 24 } })
    expect(store.scoreProgress).toBe(null)
  })
})

describe('stockStore — mode', () => {
  it('defaults to turnover', () => {
    const store = useStockStore()
    expect(store.mode).toBe('turnover')
  })

  it('setMode accepts buy_score', () => {
    const store = useStockStore()
    store.setMode('buy_score')
    expect(store.mode).toBe('buy_score')
  })
})
