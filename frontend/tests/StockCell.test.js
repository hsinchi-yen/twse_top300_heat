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

    it('uses eligible_count as denominator when present (matches pass_rate)', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 18, max_score: 24, eligible_count: 23 } })
      expect(w.find('.cell-score').text()).toContain('18/23')
    })

    it('handles score of zero correctly (not treated as N/A when max_score is valid)', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 0, max_score: 24 } })
      expect(w.find('.cell-score').text()).toContain('0/24')
      expect(w.find('.cell-score').text()).not.toContain('N/A')
    })

    it('handles perfect score', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 24, max_score: 24 } })
      expect(w.find('.cell-score').text()).toContain('24/24')
    })

    it('shows N/A when max_score is 0 (invalid score — no analyzable criteria)', () => {
      const w = mountCell({ scoresLoaded: true, scoresFetching: false, buyScore: { score: 0, max_score: 0 } })
      expect(w.find('.cell-score').text()).toContain('N/A')
      expect(w.find('.cell-score').text()).not.toContain('0/0')
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

  describe('turnover value in buy_score mode', () => {
    it('shows turnover_rate between volume and price change', () => {
      const w = mountCell({ mode: 'buy_score', scoresLoaded: true, buyScore: { score: 18, max_score: 24 } })
      expect(w.find('.cell-turnover').exists()).toBe(true)
      expect(w.find('.cell-turnover').text()).toBe('0.82%')
    })

    it('shows dash when turnover_rate is missing', () => {
      setActivePinia(createPinia())
      const w = mount(StockCell, {
        props: { stock: makeStock({ turnover_rate: null }), mode: 'buy_score', scoresLoaded: true, buyScore: null },
      })
      expect(w.find('.cell-turnover').text()).toBe('—')
    })

    it('does NOT render turnover in volume/turnover modes', () => {
      expect(mountCell({ mode: 'turnover' }).find('.cell-turnover').exists()).toBe(false)
      expect(mountCell({ mode: 'volume' }).find('.cell-turnover').exists()).toBe(false)
    })
  })

  describe('fundamentals uptrend badge', () => {
    it('shows ✅ badge in buy_score mode when fundamentals_uptrend is true', () => {
      const w = mountCell({
        mode: 'buy_score', scoresLoaded: true,
        buyScore: { score: 18, max_score: 24, fundamentals_uptrend: true },
      })
      expect(w.find('.cell-fundamentals-badge').exists()).toBe(true)
      expect(w.find('.cell-fundamentals-badge').text()).toContain('✅')
    })

    it('hides badge when fundamentals_uptrend is false', () => {
      const w = mountCell({
        mode: 'buy_score', scoresLoaded: true,
        buyScore: { score: 18, max_score: 24, fundamentals_uptrend: false },
      })
      expect(w.find('.cell-fundamentals-badge').exists()).toBe(false)
    })

    it('hides badge when buyScore is null', () => {
      const w = mountCell({ mode: 'buy_score', scoresLoaded: true, scoresFetching: false, buyScore: null })
      expect(w.find('.cell-fundamentals-badge').exists()).toBe(false)
    })

    it('shows badge outside buy_score mode when fundamentals_uptrend is true', () => {
      expect(mountCell({
        mode: 'turnover', scoresLoaded: true,
        buyScore: { score: 18, max_score: 24, fundamentals_uptrend: true },
      }).find('.cell-fundamentals-badge').exists()).toBe(true)

      expect(mountCell({
        mode: 'volume', scoresLoaded: true,
        buyScore: { score: 18, max_score: 24, fundamentals_uptrend: true },
      }).find('.cell-fundamentals-badge').exists()).toBe(true)
    })
  })

  describe('signal badge, tint and pass rate', () => {
    const rich = (o = {}) => ({
      score: 18, max_score: 24, eligible_count: 23, pass_rate: 78.3,
      signal: 'strong_buy', signal_label: '建議買進', risk_score: 0, risk_flags: [],
      fundamentals_uptrend: false, pe: { current: 30, median: 24.5, p25: 19.8 }, ...o,
    })

    it('shows signal badge with engine label', () => {
      const w = mountCell({ mode: 'buy_score', scoresLoaded: true, buyScore: rich() })
      expect(w.find('.cell-signal').text()).toBe('建議買進')
    })

    it('tints card by signal in buy_score mode', () => {
      const w = mountCell({ mode: 'buy_score', scoresLoaded: true, buyScore: rich() })
      expect(w.attributes('data-signal')).toBe('strong_buy')
      expect(w.attributes('style')).toContain('var(--sig-strong_buy-bg)')
    })

    it('marks high-risk stocks as avoid', () => {
      const w = mountCell({
        mode: 'buy_score', scoresLoaded: true,
        buyScore: rich({ signal: 'neutral', signal_label: '高風險避開', risk_score: 2 }),
      })
      expect(w.attributes('data-signal')).toBe('avoid')
      expect(w.find('.cell-signal').text()).toBe('高風險避開')
    })

    it('keeps price-heat tint (no data-signal) in volume / turnover modes', () => {
      for (const mode of ['volume', 'turnover']) {
        const w = mountCell({ mode, scoresLoaded: true, buyScore: rich() })
        expect(w.attributes('data-signal')).toBeUndefined()
        expect(w.attributes('style')).toContain('var(--tier-lr-bg)')
      }
    })

    it('still shows the signal badge outside buy_score mode', () => {
      const w = mountCell({ mode: 'volume', scoresLoaded: true, buyScore: rich() })
      expect(w.find('.cell-signal').text()).toBe('建議買進')
    })

    it('shows pass rate as big number + bar in buy_score mode', () => {
      const w = mountCell({ mode: 'buy_score', scoresLoaded: true, buyScore: rich() })
      expect(w.find('.cell-passrate').text()).toBe('78%')
      expect(w.find('.cell-passbar-fill').attributes('style')).toContain('width: 78.3%')
    })

    it('legacy entry: no signal, no pass rate, score still shown', () => {
      const w = mountCell({ mode: 'buy_score', scoresLoaded: true, buyScore: { score: 18, max_score: 24 } })
      expect(w.find('.cell-signal').exists()).toBe(false)
      expect(w.find('.cell-passrate').exists()).toBe(false)
      expect(w.attributes('data-signal')).toBeUndefined()
      expect(w.find('.cell-score').text()).toContain('18/24')
    })
  })

  describe('indicator chips', () => {
    it('shows 💲低估 when P/E below p25', () => {
      const w = mountCell({
        mode: 'buy_score', scoresLoaded: true,
        buyScore: { score: 18, max_score: 24, pe: { current: 15, median: 24, p25: 18 } },
      })
      const chip = w.find('[data-chip="value"]')
      expect(chip.text()).toContain('💲')
      expect(chip.text()).toContain('低估')
    })

    it('shows ⚠N only when risk_score > 0', () => {
      const withRisk = mountCell({
        mode: 'turnover', scoresLoaded: true,
        buyScore: { score: 10, max_score: 24, risk_score: 1, risk_flags: [{ category: 'x', name: '連續虧損' }] },
      })
      expect(withRisk.find('[data-chip="risk"]').text()).toContain('1')
      const clean = mountCell({ mode: 'turnover', scoresLoaded: true, buyScore: { score: 10, max_score: 24, risk_score: 0 } })
      expect(clean.find('[data-chip="risk"]').exists()).toBe(false)
    })

    it('renders no chip row when there is nothing to show', () => {
      const w = mountCell({ scoresLoaded: true, buyScore: { score: 10, max_score: 24 } })
      expect(w.find('.cell-chips').exists()).toBe(false)
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

describe('StockCell — daily signal chips', () => {
  it('renders institutional and MA chips from daily signals', () => {
    setActivePinia(createPinia())
    const w = mount(StockCell, {
      props: {
        stock: { stock_id: '2330', name: '台積電', rank: 1, color_tier: 'neutral', sector: '半導體', volume: 1000 },
        daily: { inst_streak: 3, inst_net_5d: 100, above_ma20: true, above_ma60: false, vol_ratio: 1.0 },
      },
    })
    expect(w.find('[data-chip="inst"]').text()).toContain('+3')
    expect(w.find('[data-chip="ma"]').text()).toContain('月線上')
  })
})
