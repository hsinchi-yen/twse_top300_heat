/**
 * StockCell.test.js — TDD component tests for buy score display
 *
 * Tests that the scoreLabel computed property and template rendering
 * behave correctly under all combinations of scoresLoaded and buyScore.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import StockCell from '../src/components/StockCell.vue'

function makeStock(overrides = {}) {
  return {
    stock_id: '2330',
    name: '台積電',
    rank: 1,
    volume: 50000000,
    turnover_rate: 0.82,
    price_change_pct: 2.35,
    color_tier: 'light_red',
    close_price: 995.0,
    sector: '半導體',
    ...overrides,
  }
}

function mountCell(props = {}) {
  setActivePinia(createPinia())
  return mount(StockCell, {
    props: {
      stock: makeStock(),
      mode: 'turnover',
      highlighted: false,
      scoresLoaded: false,
      buyScore: null,
      ...props,
    },
  })
}

describe('StockCell — buy score display', () => {
  describe('when scores not yet loaded (scoresLoaded = false)', () => {
    it('shows stock name', () => {
      const w = mountCell({ scoresLoaded: false })
      expect(w.find('.cell-name-text').text()).toBe('台積電')
    })

    it('does NOT show any score text', () => {
      const w = mountCell({ scoresLoaded: false })
      expect(w.find('.cell-score').exists()).toBe(false)
    })
  })

  describe('when scores loaded and stock has a score', () => {
    it('shows stock name', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 18, max_score: 24 } })
      expect(w.find('.cell-name-text').text()).toBe('台積電')
    })

    it('shows score in format "score/max_score"', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 18, max_score: 24 } })
      expect(w.find('.cell-score').text()).toContain('18/24')
    })

    it('includes the dash separator', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 18, max_score: 24 } })
      expect(w.find('.cell-score').text()).toContain('-')
    })

    it('handles score of zero correctly (not treated as N/A)', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 0, max_score: 24 } })
      expect(w.find('.cell-score').text()).toContain('0/24')
      expect(w.find('.cell-score').text()).not.toContain('N/A')
    })

    it('handles perfect score', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 24, max_score: 24 } })
      expect(w.find('.cell-score').text()).toContain('24/24')
    })
  })

  describe('when scores loaded but stock has no score (buyScore = null)', () => {
    it('shows N/A when fetch is complete', () => {
      const w = mountCell({ scoresLoaded: true, scoresFetching: false, buyScore: null })
      expect(w.find('.cell-score').text()).toContain('N/A')
    })

    it('shows stock name alongside N/A', () => {
      const w = mountCell({ scoresLoaded: true, scoresFetching: false, buyScore: null })
      expect(w.find('.cell-name-text').text()).toBe('台積電')
    })
  })

  describe('when scores partially loaded (scoresLoaded = true, scoresFetching = true)', () => {
    it('shows ... for stocks not yet scored', () => {
      const w = mountCell({ scoresLoaded: true, scoresFetching: true, buyScore: null })
      expect(w.find('.cell-score').text()).toContain('...')
    })

    it('does NOT show N/A while still fetching', () => {
      const w = mountCell({ scoresLoaded: true, scoresFetching: true, buyScore: null })
      expect(w.find('.cell-score').text()).not.toContain('N/A')
    })

    it('shows actual score for stocks already scored', () => {
      const w = mountCell({ scoresLoaded: true, scoresFetching: true, buyScore: { score: 18, max_score: 24 } })
      expect(w.find('.cell-score').text()).toContain('18/24')
    })
  })

  describe('existing display elements are unaffected', () => {
    it('still shows rank', () => {
      const w = mountCell()
      expect(w.find('.cell-rank').text()).toContain('#1')
    })

    it('still shows sector', () => {
      const w = mountCell()
      expect(w.find('.cell-sector').text()).toBe('半導體')
    })

    it('still shows stock_id', () => {
      const w = mountCell()
      expect(w.find('.cell-code').text()).toBe('2330')
    })

    it('still shows price change', () => {
      const w = mountCell()
      expect(w.find('.cell-pct').text()).toContain('2.35')
    })
  })
})
