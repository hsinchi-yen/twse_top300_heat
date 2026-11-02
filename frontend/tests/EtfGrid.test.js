/** EtfGrid.test.js — ETF view: sort, type filter, pagination, degraded states. */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import EtfGrid from '../src/components/EtfGrid.vue'
import { useStockStore } from '../src/stores/stockStore'

const etf = (i, over = {}) => ({
  etf_id: `00${i}`, name: `ETF${i}`, etf_type: i % 2 ? '國內股' : '槓桿',
  turnover_rank: i, asset_scale_rank: 100 - i, volume: 1000, color_tier: 'neutral', ...over,
})

function seed(n = 40) {
  const store = useStockStore()
  store.setEtfData({ etfs: Array.from({ length: n }, (_, i) => etf(i + 1)), date: 'd' })
  return store
}

const names = (w) => w.findAll('.cell-name-text').map(n => n.text())

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

describe('EtfGrid', () => {
  it('ranks by turnover by default', () => {
    seed()
    expect(names(mount(EtfGrid)).slice(0, 2)).toEqual(['ETF1', 'ETF2'])
  })

  it('re-sorts by asset scale and returns to page one', async () => {
    const store = seed()
    const w = mount(EtfGrid)
    await w.find('.page-next').trigger('click')
    store.setEtfSortBy('asset_scale')
    await nextTick()
    expect(names(w)[0]).toBe('ETF40')
    expect(w.find('.pager-page').text()).toBe('1 / 2')
  })

  it('breaks rank ties by volume, unranked last', () => {
    useStockStore().setEtfData({
      etfs: [
        etf(1, { turnover_rank: null, volume: 9 }),
        etf(2, { turnover_rank: 5, volume: 1, name: 'low' }),
        etf(3, { turnover_rank: 5, volume: 2, name: 'high' }),
      ],
    })
    expect(names(mount(EtfGrid))).toEqual(['high', 'low', 'ETF1'])
  })

  it('counts types and filters by them', async () => {
    seed(6)
    const w = mount(EtfGrid)
    const chips = w.findAll('.type-chip')
    expect(chips.map(c => c.text())).toEqual(['全部 6', '國內股 3', '槓桿 3'])
    await chips[2].trigger('click')
    expect(w.findAll('.etf-cell')).toHaveLength(3)
    await chips[2].trigger('click')
    expect(w.findAll('.etf-cell')).toHaveLength(6)
  })

  it('全部 clears every type filter', async () => {
    seed(6)
    const w = mount(EtfGrid)
    await w.findAll('.type-chip')[1].trigger('click')
    await w.findAll('.type-chip')[0].trigger('click')
    expect(w.findAll('.etf-cell')).toHaveLength(6)
    expect(w.findAll('.type-chip')[0].classes()).toContain('active')
  })

  it('a poll keeps the page, a shrinking list clamps it', async () => {
    const store = seed(40)
    const w = mount(EtfGrid)
    await w.find('.page-next').trigger('click')
    store.setEtfData({ etfs: Array.from({ length: 40 }, (_, i) => etf(i + 1)) })
    await nextTick()
    expect(w.find('.pager-page').text()).toBe('2 / 2')
    store.setEtfData({ etfs: [etf(1)] })
    await nextTick()
    await nextTick()
    expect(w.find('.pager-page').text()).toBe('1 / 1')
  })

  it('follows the density setting', async () => {
    const store = seed()
    const w = mount(EtfGrid)
    expect(w.findAll('.etf-cell')).toHaveLength(25)
    store.setGridSize(4)
    await nextTick()
    expect(w.findAll('.etf-cell')).toHaveLength(16)
  })

  it('states loading, failure and emptiness, and keeps data on a failed poll', () => {
    const store = useStockStore()
    store.setEtfLoading(true)
    expect(mount(EtfGrid).find('.state-msg').text()).toContain('載入')
    store.setEtfLoading(false)
    expect(mount(EtfGrid).find('.state-msg').text()).toContain('暫無')
    store.setEtfError('HTTP 500')
    expect(mount(EtfGrid).find('.state-msg').text()).toContain('HTTP 500')
    seed(3)
    store.setEtfError('HTTP 500')
    expect(mount(EtfGrid).findAll('.etf-cell')).toHaveLength(3)
  })
})
