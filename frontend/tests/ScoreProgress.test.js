/**
 * ScoreProgress.test.js — progress bar + last-updated label.
 *
 * While fetching: shows N/M and a percentage from the display pool.
 * When idle: shows the last-updated date/time from generated_at.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ScoreProgress from '../src/components/ScoreProgress.vue'
import { useStockStore } from '../src/stores/stockStore'

const SECTORS = [
  { name: '半導體', stocks: [{ stock_id: '2330' }, { stock_id: '2454' }] },
  { name: '金融', stocks: [{ stock_id: '2881' }, { stock_id: '2882' }] },
]

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountWith(setup) {
  const store = useStockStore()
  store.setData({ sectors: SECTORS })
  setup(store)
  return mount(ScoreProgress)
}

describe('ScoreProgress — while fetching', () => {
  it('renders the progress bar and count', () => {
    const w = mountWith((store) => {
      store.setScoresFetching(true)
      store.setPartialScores({ '2330': { score: 18, max_score: 24 } })
    })
    expect(w.find('.sp-bar').exists()).toBe(true)
    expect(w.find('.sp-text').text()).toContain('1/4')
    expect(w.find('.sp-text').text()).toContain('25%')
  })

  it('caps progress at 100%', () => {
    const w = mountWith((store) => {
      store.setScoresFetching(true)
      store.setPartialScores({
        '2330': { score: 1, max_score: 24 }, '2454': { score: 1, max_score: 24 },
        '2881': { score: 1, max_score: 24 }, '2882': { score: 1, max_score: 24 },
      })
    })
    expect(w.find('.sp-text').text()).toContain('100%')
  })

  it('ignores invalid scores (max_score 0) in the count', () => {
    const w = mountWith((store) => {
      store.setScoresFetching(true)
      store.setPartialScores({ '2330': { score: 0, max_score: 0 } })
    })
    expect(w.find('.sp-text').text()).toContain('0/4')
  })
})

describe('ScoreProgress — when idle', () => {
  it('shows the last-updated date and time from generated_at', () => {
    const w = mountWith((store) => {
      store.setScores({ '2330': { score: 18, max_score: 24 } })
      store.setScoreMeta('2026-06-01', '2026-06-01T03:42:18+08:00')
    })
    expect(w.find('.sp-bar').exists()).toBe(false)
    // Date/time render is timezone-dependent; assert structure, not exact value.
    expect(w.find('.sp-done').text()).toContain('評分更新')
    expect(w.find('.sp-done').text()).toMatch(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/)
  })

  it('falls back to scoreDate when generated_at is absent', () => {
    const w = mountWith((store) => {
      store.setScores({ '2330': { score: 18, max_score: 24 } })
      store.setScoreMeta('2026-06-01', '')
    })
    expect(w.find('.sp-done').text()).toContain('2026-06-01')
  })

  it('renders nothing when there is no score metadata', () => {
    const w = mountWith(() => {})
    expect(w.find('.sp-bar').exists()).toBe(false)
    expect(w.find('.sp-done').exists()).toBe(false)
  })
})
