/**
 * FilterBar.test.js — 篩選列 UI + HeatmapGrid integration (filters narrow the
 * same 600-stock payload; mode switches keep the selection).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import FilterBar from '../src/components/FilterBar.vue'
import HeatmapGrid from '../src/components/HeatmapGrid.vue'
import { useFilterStore } from '../src/stores/filterStore'
import { useStockStore } from '../src/stores/stockStore'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ items: [] }) })))
})

describe('FilterBar', () => {
  it('renders the four presets and the match count', () => {
    const w = mount(FilterBar, { props: { matched: 37, total: 600 } })
    expect(w.findAll('.preset-btn').map(b => b.text())).toEqual(['穩健優質', '轉強起漲', '低估待買', '量增突破'])
    expect(w.find('.filter-count').exists()).toBe(false)   // no filter active → no count
  })

  it('clicking a preset activates it and shows 符合 N / total', async () => {
    const w = mount(FilterBar, { props: { matched: 37, total: 600 } })
    await w.findAll('.preset-btn')[0].trigger('click')
    expect(useFilterStore().active).toEqual(['pass75', 'noRisk'])
    expect(w.findAll('.preset-btn')[0].classes()).toContain('active')
    expect(w.find('.filter-count').text()).toBe('符合 37 / 600')
  })

  it('clicking the active preset again clears the filter', async () => {
    const w = mount(FilterBar, { props: { matched: 1, total: 600 } })
    await w.findAll('.preset-btn')[1].trigger('click')
    await w.findAll('.preset-btn')[1].trigger('click')
    expect(useFilterStore().active).toEqual([])
  })

  it('custom panel toggles individual conditions', async () => {
    const w = mount(FilterBar, { props: { matched: 1, total: 600 } })
    await w.find('.custom-toggle').trigger('click')
    const box = w.find('[data-cond="instBuy3"]')
    await box.trigger('click')
    expect(useFilterStore().active).toEqual(['instBuy3'])
    expect(box.classes()).toContain('active')
  })

  it('clear button empties the selection', async () => {
    const w = mount(FilterBar, { props: { matched: 1, total: 600 } })
    await w.findAll('.preset-btn')[2].trigger('click')
    await w.find('.filter-clear').trigger('click')
    expect(useFilterStore().active).toEqual([])
  })
})

describe('HeatmapGrid with filters', () => {
  function seed(mode) {
    const s = useStockStore()
    s.setMode(mode)
    s.setData({
      sectors: [{
        name: '半導體',
        stocks: [
          { stock_id: 'A', name: '甲', rank: 1, volume: 900, turnover_rate: 1, price_change_pct: 1, color_tier: 'neutral' },
          { stock_id: 'B', name: '乙', rank: 2, volume: 800, turnover_rate: 2, price_change_pct: 1, color_tier: 'neutral' },
          { stock_id: 'C', name: '丙', rank: 3, volume: 700, turnover_rate: 3, price_change_pct: 1, color_tier: 'neutral' },
        ],
      }],
      date: '2026-10-23', market_open: false,
    })
    s.setScores({
      A: { score: 18, max_score: 24, pass_rate: 76, risk_score: 0 },
      B: { score: 12, max_score: 24, pass_rate: 50, risk_score: 0 },
      C: { score: 20, max_score: 24, pass_rate: 90, risk_score: 0 },
    })
  }

  const names = (w) => w.findAll('.cell-name-text').map(n => n.text())

  it('shows all stocks without filters', () => {
    seed('volume')
    expect(names(mount(HeatmapGrid))).toEqual(['甲', '乙', '丙'])
  })

  it('preset narrows the list and sorts by pass_rate desc', async () => {
    seed('volume')
    useFilterStore().applyPreset('quality')
    const w = mount(HeatmapGrid)
    await nextTick()
    expect(names(w)).toEqual(['丙', '甲'])
    expect(w.find('.filter-count').text()).toBe('符合 2 / 3')
  })

  it('keeps the filter across mode switches', async () => {
    seed('turnover')
    useFilterStore().applyPreset('quality')
    const w = mount(HeatmapGrid)
    useStockStore().setMode('buy_score')
    await nextTick()
    expect(names(w)).toEqual(['丙', '甲'])
    expect(w.findAll('.cell-rank').map(r => r.text())).toEqual(['#1', '#2'])
  })
})
