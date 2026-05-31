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

  it('ignores unknown density values', () => {
    const store = useStockStore()
    store.setMobileDensity('3x3')
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
