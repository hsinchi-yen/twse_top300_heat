/**
 * app.integration.test.js — mounts the whole App against the contract-shaped fake
 * API and walks the investor's path: read the market, open a candidate, size a
 * position, pin it. Also pins the project invariants that must survive any UI
 * change (fixed stock query, no token, honest degraded states).
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import App from '../src/App.vue'
import { useUiStore } from '../src/stores/uiStore'
import { useStockStore } from '../src/stores/stockStore'
import { fakeApi, emptyBacktest, emptyTrend } from './helpers/fakeApi'

let wrapper

async function mountApp() {
  wrapper = mount(App, { attachTo: document.body })
  await flushPromises()
  await nextTick()
  await flushPromises()
  return wrapper
}

const stockCalls = (calls) => calls.filter(c => c.path.startsWith('/api/stocks/top100'))

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('investor path', () => {
  it('lands on the overview and reads the market', async () => {
    fakeApi()
    const w = await mountApp()
    expect(w.find('#nav-overview').classes()).toContain('active')
    expect(w.find('.read-title').exists()).toBe(true)
    expect(w.find('.pulse').text()).toContain('上漲 / 下跌')
  })

  it('lists only stocks that qualify, with the reason', async () => {
    fakeApi()
    const w = await mountApp()
    const rows = w.findAll('.shortlist .row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('台積電')
    expect(rows[0].find('.row-why').text()).toContain('19/23')
  })

  it('renders breadth, sectors and setup validation from the API', async () => {
    fakeApi()
    const w = await mountApp()
    expect(w.find('.breadth svg').exists()).toBe(true)
    expect(w.find('.sector-table').text()).toContain('半導體')
    expect(w.find('[data-setup="trend_up"]').text()).toContain('7 / 11 期')
    expect(w.find('[data-setup="breakout"]').text()).toContain('樣本不足')
    expect(w.find('.setups .caveat').text()).toContain('倖存者偏差')
    expect(w.find('.setups .caveat').text()).toContain('次一交易日')
    expect(w.find('.setups .caveat').text()).toContain('超額只計')
    expect(w.find('.data-time').text()).toBe('08/09 14:00')
    expect(w.find('.breadth').text()).toContain('倖存者偏差')
    expect(w.find('.sectors').text()).toContain('倖存者偏差')
  })

  it('opens the stock panel with verdict, trend, flows, sizing and criteria', async () => {
    const { calls } = fakeApi()
    const w = await mountApp()
    await w.find('.shortlist .row-open').trigger('click')
    await flushPromises()

    const drawer = w.find('.drawer')
    expect(drawer.attributes('role')).toBe('dialog')
    expect(drawer.find('.head-name').text()).toBe('台積電')
    expect(drawer.find('.stance-tag').text()).toBe('研究候選')
    expect(drawer.findAll('.dim')).toHaveLength(4)
    expect(drawer.findAll('svg .line')).not.toHaveLength(0)
    expect(drawer.find('.tiles').text()).toContain('連買 4 日')
    expect(drawer.find('.sizer-lots').exists()).toBe(true)
    expect(drawer.find('.crit--pass').text()).toContain('ROE')
    expect(drawer.find('.research-note').text()).toContain('非投資建議')
    expect(calls.some(c => c.path === '/api/stocks/2330/history')).toBe(true)
    expect(calls.some(c => c.path === '/api/scores/2330/history')).toBe(true)
  })

  it('pins from the panel and the watchlist count follows', async () => {
    const { calls } = fakeApi()
    const w = await mountApp()
    useUiStore().openStock('2330')
    await flushPromises()
    await w.find('.drawer-pin').trigger('click')
    await flushPromises()
    expect(calls.some(c => c.path === '/api/watchlist/2330' && c.method === 'PUT')).toBe(true)
    expect(w.find('#nav-watchlist').text()).toContain('1')
    expect(w.find('.drawer-pin').attributes('aria-pressed')).toBe('true')
  })

  it('Esc closes the panel and returns focus', async () => {
    fakeApi()
    const w = await mountApp()
    const opener = w.find('.shortlist .row-open')
    opener.element.focus()
    await opener.trigger('click')
    await flushPromises()
    expect(document.activeElement).toBe(w.find('.drawer').element)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(w.find('.drawer').exists()).toBe(false)
    expect(document.activeElement).toBe(opener.element)
  })

  it('clicking a heatmap card opens the same panel', async () => {
    fakeApi()
    const w = await mountApp()
    await w.find('#nav-heatmap').trigger('click')
    await flushPromises()
    await w.findAll('.stock-cell')[0].trigger('click')
    await flushPromises()
    expect(w.find('.drawer').exists()).toBe(true)
  })

  it('global search finds by name and opens the panel', async () => {
    fakeApi()
    const w = await mountApp()
    const input = w.find('.search-input')
    await input.trigger('focus')
    await input.setValue('聯')
    expect(w.findAll('.search-item')).toHaveLength(2)
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(w.find('.head-name').text()).toBe('聯發科')
  })

  it('/ does not pull focus out of an open panel', async () => {
    fakeApi()
    const w = await mountApp()
    useUiStore().openStock('2330')
    await flushPromises()
    await nextTick()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }))
    expect(document.activeElement).not.toBe(w.find('.search-input').element)
  })

  it('search explains an empty result', async () => {
    fakeApi()
    const w = await mountApp()
    const input = w.find('.search-input')
    await input.trigger('focus')
    await input.setValue('9999')
    expect(w.find('.search-empty').text()).toContain('9999')
  })

  it('opens the guide, which leads with the limits of the tool', async () => {
    fakeApi()
    const w = await mountApp()
    await w.find('.guide-btn').trigger('click')
    const guide = w.find('.guide')
    expect(guide.find('.guide-limits').text()).toContain('不保證獲利')
    await guide.find('.guide-close').trigger('click')
    expect(w.find('.guide').exists()).toBe(false)
  })

  it('switching the setup horizon refetches for that horizon', async () => {
    const { calls } = fakeApi()
    const w = await mountApp()
    const button = w.findAll('.setups .segmented__item').find(b => b.text() === '60 日')
    await button.trigger('click')
    await flushPromises()
    expect(calls.some(c => c.path === '/api/market/backtest?horizon=60')).toBe(true)
    expect(button.classes()).toContain('active')
  })
})

describe('sector drill-down', () => {
  const mixed = [
    { stock_id: '2330', name: '台積電', rank: 1, volume: 3, turnover_rate: 1, price_change_pct: 1, color_tier: 'neutral', close_price: 100 },
    { stock_id: '2881', name: '富邦金', rank: 2, volume: 2, turnover_rate: 2, price_change_pct: 1, color_tier: 'neutral', close_price: 100 },
    { stock_id: '2882', name: '國泰金', rank: 3, volume: 1, turnover_rate: 3, price_change_pct: 1, color_tier: 'neutral', close_price: 100 },
    { stock_id: '2891', name: '中信金', rank: 4, volume: 1, turnover_rate: 4, price_change_pct: 1, color_tier: 'neutral', close_price: 100 },
  ]

  async function openFinance() {
    const api = fakeApi({
      sectors: [{ name: '半導體', stocks: mixed.slice(0, 1) }, { name: '金融', stocks: mixed.slice(1) }],
    })
    const w = await mountApp()
    await w.findAll('.sector-open').find(b => b.text().includes('金融')).trigger('click')
    await flushPromises()
    return { w, api }
  }

  it('opens the heatmap limited to that sector, with a removable chip', async () => {
    const { w } = await openFinance()
    expect(w.findAll('.cell-name-text').map(n => n.text()).sort()).toEqual(['中信金', '國泰金', '富邦金'].sort())
    expect(w.find('.sector-chip').text()).toContain('金融')
    expect(w.find('.filter-count').text()).toBe('符合 3 / 4')
    await w.find('.sector-chip').trigger('click')
    expect(w.findAll('.cell-name-text')).toHaveLength(4)
  })

  it('never changes the stock query', async () => {
    const { api } = await openFinance()
    for (const c of stockCalls(api.calls)) expect(c.path).toBe('/api/stocks/top100?mode=volume&limit=600')
  })
})

describe('project invariants', () => {
  it('every stock fetch uses mode=volume&limit=600, whatever the sort', async () => {
    const { calls } = fakeApi()
    const w = await mountApp()
    await w.find('#nav-heatmap').trigger('click')
    await flushPromises()
    for (const id of ['#sort-volume', '#sort-buy_score', '#sort-turnover']) {
      await w.find(id).trigger('click')
      await flushPromises()
    }
    const list = stockCalls(calls)
    expect(list.length).toBeGreaterThan(1)
    for (const c of list) expect(c.path).toBe('/api/stocks/top100?mode=volume&limit=600')
  })

  it('never sends a token', async () => {
    const { fetchMock } = fakeApi()
    await mountApp()
    for (const [url, init] of fetchMock.mock.calls) {
      expect(String(url)).not.toMatch(/token/i)
      expect(JSON.stringify(init?.headers ?? {})).not.toMatch(/token/i)
    }
  })

  it('heatmap sort changes order without a new query shape', async () => {
    fakeApi()
    const w = await mountApp()
    await w.find('#nav-heatmap').trigger('click')
    await flushPromises()
    await w.find('#sort-turnover').trigger('click')
    await flushPromises()
    expect(w.findAll('.cell-name-text')[0].text()).toBe('聯發科')
    await w.find('#sort-volume').trigger('click')
    await flushPromises()
    expect(w.findAll('.cell-name-text')[0].text()).toBe('台積電')
  })

  it('the heatmap tab returns to the last sort used', async () => {
    fakeApi()
    const w = await mountApp()
    await w.find('#nav-heatmap').trigger('click')
    await flushPromises()
    await w.find('#sort-buy_score').trigger('click')
    await w.find('#nav-overview').trigger('click')
    await flushPromises()
    await w.find('#nav-heatmap').trigger('click')
    expect(useStockStore().mode).toBe('buy_score')
  })

  it('a poll does not throw the reader back to page one', async () => {
    const many = Array.from({ length: 50 }, (_, i) => ({
      stock_id: String(1000 + i), name: `股${i}`, rank: i + 1, volume: 1000, turnover_rate: 50 - i,
      price_change_pct: 0, color_tier: 'neutral', close_price: 10,
    }))
    fakeApi({ stocks: many })
    const w = await mountApp()
    await w.find('#nav-heatmap').trigger('click')
    await flushPromises()
    await w.find('.page-next').trigger('click')
    expect(w.find('.pager-page').text()).toBe('2 / 2')
    useStockStore().setData({
      sectors: [{ name: '半導體', stocks: many.map(s => ({ ...s, close_price: 11 })) }],
      date: '2026-08-09', market_open: false,
    })
    await nextTick()
    expect(w.find('.pager-page').text()).toBe('2 / 2')
  })
})

describe('degraded states stay honest', () => {
  it('shows no candidates and no invented score before the nightly job has run', async () => {
    fakeApi({ scores: {}, signals: {}, trend: emptyTrend, backtest: emptyBacktest })
    const w = await mountApp()
    expect(w.findAll('.shortlist .row')).toHaveLength(0)
    expect(w.find('.shortlist .empty').text()).toContain('尚無評分資料')
    expect(w.find('.read-title').text()).toBe('尚無判讀')
    expect(w.find('.breadth .empty').text()).toContain('累積')
    expect(w.find('.setups .empty').text()).toContain('歷史資料不足')
  })

  it('scores without nightly signals read as missing data, not as no candidates', async () => {
    fakeApi({ signals: {}, trend: emptyTrend, backtest: emptyBacktest })
    const w = await mountApp()
    expect(w.find('.shortlist .empty').text()).toContain('盤後指標尚未產生')
  })

  it('with full data and nothing qualifying, it says so without telling the reader what to do', async () => {
    fakeApi({ scores: { 2330: { score: 2, max_score: 24, eligible_count: 20, pass_rate: 10, signal: 'neutral', signal_label: '不建議買進', risk_score: 0 } } })
    const w = await mountApp()
    const text = w.find('.shortlist .empty').text()
    expect(text).toContain('沒有股票同時滿足條件')
    expect(text).not.toMatch(/不必|應該|進場/)
  })

  it('the panel shows 資料不足, not a number, when a stock has no score', async () => {
    fakeApi({ scores: {}, signals: {} })
    const w = await mountApp()
    useUiStore().openStock('2303')
    await flushPromises()
    expect(w.find('.composite-value').text()).toBe('—')
    expect(w.find('.stance-tag').text()).toBe('資料不足')
    expect(w.findAll('.dim-value').every(d => d.text() === '無資料')).toBe(true)
  })

  it('a stock outside the pool still opens from its watchlist quote', async () => {
    fakeApi({
      watchlist: [{ stock_id: '6488', note: '', added_at: 't', quote: { stock_id: '6488', name: '環球晶', sector: '半導體', close_price: 50, price_change_pct: 1 } }],
    })
    const w = await mountApp()
    useUiStore().openStock('6488')
    await flushPromises()
    expect(w.find('.head-name').text()).toBe('環球晶')
  })

  it('analytics failing does not take the overview down', async () => {
    fakeApi({ failing: ['/api/market'] })
    const w = await mountApp()
    expect(w.find('.shortlist .row').exists()).toBe(true)
    expect(w.find('.breadth .empty').exists()).toBe(true)
  })

  it('history failing is reported in the panel; the rest still renders', async () => {
    fakeApi({ failing: ['/api/stocks/2330/history'] })
    const w = await mountApp()
    useUiStore().openStock('2330')
    await flushPromises()
    expect(w.find('.drawer').text()).toContain('走勢暫時無法取得')
    expect(w.find('.composite-value').text()).not.toBe('—')
  })

  it('reports a stock API failure instead of an empty screen', async () => {
    fakeApi({ failing: ['/api/stocks/top100'] })
    const w = await mountApp()
    expect(w.find('.overview .state-msg.error').text()).toContain('無法取得行情')
  })
})
