/**
 * components.test.js — card interaction, ETF card honesty, position sizer UI,
 * stock history races.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, ref } from 'vue'
import StockCell from '../src/components/StockCell.vue'
import EtfCell from '../src/components/EtfCell.vue'
import PositionSizer from '../src/components/PositionSizer.vue'
import { useStockHistory } from '../src/composables/useStockHistory'
import { useMarketStore } from '../src/stores/marketStore'
import SetupPanel from '../src/components/overview/SetupPanel.vue'
import { dataTimeLabel, formatLots, formatPct, formatPrice, formatSignedLots, formatTurnover, formatTwd, pctClass, shortDate } from '../src/utils/format'

const stock = { stock_id: '2330', name: '台積電', rank: 1, color_tier: 'neutral', sector: '半導體' }

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

// jsdom has no PointerEvent, and VTU cannot assign clientX on a MouseEvent.
async function pointer(w, type, { x = 0, y = 0, pointerType = 'touch', buttons = 1 } = {}) {
  const event = new MouseEvent(type, { clientX: x, clientY: y, buttons, bubbles: true })
  Object.defineProperty(event, 'pointerType', { value: pointerType })
  w.element.dispatchEvent(event)
  await nextTick()
}

describe('StockCell — opening the panel', () => {
  const cell = (props = {}) => mount(StockCell, { props: { stock, clickable: true, pinnable: true, ...props } })

  it('click opens', async () => {
    const w = cell()
    await w.trigger('click')
    expect(w.emitted('open')[0]).toEqual(['2330'])
  })

  it('is inert unless clickable', async () => {
    const w = cell({ clickable: false })
    await w.trigger('click')
    expect(w.emitted('open')).toBeUndefined()
    expect(w.attributes('role')).toBeUndefined()
  })

  it('Enter and Space open it from the keyboard', async () => {
    const w = cell()
    await w.trigger('keydown', { key: 'Enter' })
    await w.trigger('keydown', { key: ' ' })
    expect(w.emitted('open')).toHaveLength(2)
  })

  it('Enter on the star pins without opening', async () => {
    const w = cell()
    await w.find('.cell-pin').trigger('keydown', { key: 'Enter' })
    expect(w.emitted('open')).toBeUndefined()
  })

  it('clicking the star pins without opening', async () => {
    const w = cell()
    await w.find('.cell-pin').trigger('click')
    expect(w.emitted('toggle-pin')).toHaveLength(1)
    expect(w.emitted('open')).toBeUndefined()
  })

  it('a long press pins and does not also open', async () => {
    vi.useFakeTimers()
    const w = cell()
    await pointer(w, 'pointerdown')
    vi.advanceTimersByTime(600)
    await pointer(w, 'pointerup')
    await w.trigger('click')
    expect(w.emitted('toggle-pin')).toHaveLength(1)
    expect(w.emitted('open')).toBeUndefined()
  })

  it('a swipe across the card does not open it', async () => {
    const w = cell()
    await pointer(w, 'pointerdown')
    await pointer(w, 'pointermove', { x: 80 })
    await w.trigger('click')
    expect(w.emitted('open')).toBeUndefined()
  })

  it('the next tap after a swipe opens normally', async () => {
    const w = cell()
    await pointer(w, 'pointerdown')
    await pointer(w, 'pointermove', { x: 80 })
    await w.trigger('click')
    await pointer(w, 'pointerdown')
    await w.trigger('click')
    expect(w.emitted('open')).toHaveLength(1)
  })
})

describe('EtfCell', () => {
  const etf = {
    etf_id: '0050', name: '元大台灣50', etf_type: '國內股', asset_scale: 3241.5,
    volume: 6_888_000, turnover_rate: 0.41, close_price: 185.5, price_change_pct: 1.23,
    premium_discount: 0.16, nav: 185.2, management_fee: 0.32, color_tier: 'light_red',
    portfolio_turnover: null,
  }

  it('never invents a portfolio turnover the source did not report', () => {
    expect(mount(EtfCell, { props: { etf } }).attributes('title')).toContain('持股週轉率 —')
  })

  it('shows the reported value when it exists', () => {
    const w = mount(EtfCell, { props: { etf: { ...etf, portfolio_turnover: 6 } } })
    expect(w.attributes('title')).toContain('持股週轉率 6%/年')
  })

  it('shows premium, fee, scale and turnover', () => {
    const text = mount(EtfCell, { props: { etf, rank: 2 } }).text()
    expect(text).toContain('溢 0.16%')
    expect(text).toContain('費 0.32%')
    expect(text).toContain('3242億')
    expect(text).toContain('週轉 0.410%')
  })

  it('labels a discount and hides unknown fields', () => {
    const w = mount(EtfCell, { props: { etf: { ...etf, premium_discount: -0.2, management_fee: null } } })
    expect(w.text()).toContain('折 0.20%')
    expect(w.text()).not.toContain('費')
  })

  it('falls back to volume when turnover is unknown', () => {
    const w = mount(EtfCell, { props: { etf: { ...etf, turnover_rate: null } } })
    expect(w.find('.cell-turnover').text()).toBe('689萬股')
  })
})

describe('PositionSizer', () => {
  const sizer = (props = {}) => mount(PositionSizer, { props: { price: 100, ma60: 95, avgVolume: 40_000_000, ...props } })
  const field = (w, name) => w.find(`[data-field="${name}"]`)

  it('starts from the current price and the suggested stop', () => {
    const w = sizer()
    expect(field(w, 'entry').element.value).toBe('100')
    expect(field(w, 'stop').element.value).toBe('95')
    expect(w.find('.field em').text()).toContain('季線')
  })

  it('recomputes from what the user types and drops the stop label', async () => {
    const w = sizer()
    await field(w, 'capital').setValue(10_000_000)
    await field(w, 'stop').setValue(90)
    expect(w.find('.sizer-lots').text()).toBe('10 張')
    expect(w.find('.field em').exists()).toBe(false)
  })

  it('explains invalid input instead of showing numbers', async () => {
    const w = sizer()
    await field(w, 'stop').setValue(120)
    expect(w.find('.sizer-result').exists()).toBe(false)
    expect(w.find('.sizer-invalid').exists()).toBe(true)
  })

  it('warns when the position is large against daily volume', async () => {
    const w = sizer({ avgVolume: 1000 })
    expect(w.find('[data-warning="liquidity"]').exists()).toBe(true)
  })

  it('says what is limiting the size', async () => {
    const w = sizer()
    await field(w, 'riskPct').setValue(50)
    expect(w.find('.sizer-basis').text()).toContain('單檔上限')
  })

  it('a live price update does not overwrite what the user typed', async () => {
    const w = sizer()
    await field(w, 'capital').setValue(10_000_000)
    await field(w, 'entry').setValue(98)
    await field(w, 'stop').setValue(90)
    const size = w.find('.sizer-lots').text()
    await w.setProps({ price: 101.5 })
    expect(field(w, 'entry').element.value).toBe('98')
    expect(field(w, 'stop').element.value).toBe('90')
    expect(w.find('.sizer-lots').text()).toBe(size)
  })

  it('untouched fields keep following the live price', async () => {
    const w = sizer({ ma60: null })
    await w.setProps({ price: 110 })
    expect(field(w, 'entry').element.value).toBe('110')
    expect(field(w, 'stop').element.value).toBe('101.2')
  })

  it('remembers capital and risk, but not the per-stock levels', async () => {
    const w = sizer()
    await field(w, 'capital').setValue(5_000_000)
    await nextTick()
    const saved = JSON.parse(localStorage.getItem('sizing_prefs'))
    expect(saved.capital).toBe(5_000_000)
    expect(saved.entry).toBeUndefined()
    expect(field(sizer(), 'capital').element.value).toBe('5000000')
  })

  it('survives corrupt stored settings', () => {
    localStorage.setItem('sizing_prefs', '{broken')
    expect(field(sizer(), 'capital').element.value).toBe('1000000')
  })
})

describe('useStockHistory', () => {
  function deferredFetch() {
    const pending = {}
    vi.stubGlobal('fetch', vi.fn((url) => new Promise((resolve) => { pending[url] = resolve })))
    return pending
  }
  const respond = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) })

  it('a slow answer for the previous stock cannot overwrite the current one', async () => {
    const pending = deferredFetch()
    const id = ref('1111')
    const { bars } = useStockHistory(id)
    id.value = '2222'
    await nextTick()

    pending['/api/stocks/2222/history'](respond({ bars: [{ close: 2 }], flows: [] }))
    pending['/api/scores/2222/history'](respond({ points: [] }))
    await flushPromises()
    pending['/api/stocks/1111/history'](respond({ bars: [{ close: 1 }], flows: [] }))
    pending['/api/scores/1111/history'](respond({ points: [] }))
    await flushPromises()

    expect(bars.value).toEqual([{ close: 2 }])
  })

  it('clears data as soon as the stock changes', async () => {
    const pending = deferredFetch()
    const id = ref('1111')
    const { bars, loading } = useStockHistory(id)
    pending['/api/stocks/1111/history'](respond({ bars: [{ close: 1 }], flows: [] }))
    pending['/api/scores/1111/history'](respond({ points: [] }))
    await flushPromises()
    expect(bars.value).toHaveLength(1)
    id.value = '2222'
    await nextTick()
    expect(bars.value).toEqual([])
    expect(loading.value).toBe(true)
  })

  it('does nothing without a stock', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    useStockHistory(ref(''))
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('marketStore', () => {
  it('a slower answer for an abandoned horizon is ignored', async () => {
    const pending = {}
    vi.stubGlobal('fetch', vi.fn((url) => new Promise((resolve) => { pending[url] = resolve })))
    const respond = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) })
    const market = useMarketStore()
    market.loadBacktest(5)
    market.loadBacktest(60)
    pending['/api/market/backtest?horizon=60'](respond({ horizon: 60 }))
    await flushPromises()
    pending['/api/market/backtest?horizon=5'](respond({ horizon: 5 }))
    await flushPromises()
    expect(market.backtest.horizon).toBe(60)
  })

  it('never shows one horizon\'s numbers under another\'s label', async () => {
    const respond = (body) => ({ ok: true, status: 200, json: () => Promise.resolve(body) })
    const pending = {}
    vi.stubGlobal('fetch', vi.fn((url) => new Promise((resolve) => { pending[url] = resolve })))
    const market = useMarketStore()
    market.loadBacktest(20)
    pending['/api/market/backtest?horizon=20'](respond({ horizon: 20, periods: 3, setups: [], baseline: { avg_ret: 1, win_rate: 50 } }))
    await flushPromises()

    const w = mount(SetupPanel)
    expect(w.find('.setup-table').exists()).toBe(true)
    market.loadBacktest(60)
    await nextTick()
    expect(w.find('.setup-table').exists()).toBe(false)
    expect(w.find('.empty').text()).toContain('載入')
  })

  it('says so when the selected horizon cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('down'))))
    const market = useMarketStore()
    const w = mount(SetupPanel)
    await market.loadBacktest(60)
    await nextTick()
    expect(w.find('.empty').text()).toContain('無法取得')
  })

  it('keeps the last good data when a refresh fails', async () => {
    const market = useMarketStore()
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ date: 'd' }) })))
    await market.loadTrend()
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('down'))))
    await market.loadTrend()
    expect(market.trend.date).toBe('d')
  })
})

describe('format', () => {
  it('renders missing values as a dash, never zero', () => {
    for (const f of [formatPrice, formatPct, formatLots, formatSignedLots, formatTwd]) {
      expect(f(null)).toBe('—')
      expect(f(undefined)).toBe('—')
      expect(f(NaN)).toBe('—')
    }
  })

  it('formats magnitudes for reading', () => {
    expect(formatPrice(1045)).toBe('1045.0')
    expect(formatPrice(95.5)).toBe('95.50')
    expect(formatPct(2.345)).toBe('+2.35%')
    expect(formatPct(-1, 1)).toBe('-1.0%')
    expect(formatLots(45_000_000)).toBe('4.5萬張')
    expect(formatLots(9_000_000)).toBe('9,000張')
    expect(formatSignedLots(1250)).toBe('+1,250')
    expect(formatTwd(250_000_000)).toBe('2.50 億')
    expect(formatTwd(1_500_000)).toBe('150.0 萬')
    expect(formatTwd(5850)).toBe('5,850')
    expect(shortDate('2026-10-23')).toBe('10/23')
    expect(pctClass(1)).toBe('pct-up')
    expect(pctClass(-1)).toBe('pct-down')
    expect(pctClass(0)).toBe('pct-flat')
    expect(pctClass(null)).toBe('')
  })

  it('treats a non-positive turnover as missing: a traded stock cannot have none', () => {
    expect(formatTurnover(7.7412)).toBe('7.74%')
    expect(formatTurnover(0.004)).toBe('0.00%')
    for (const missing of [0, -1, null, undefined, NaN]) expect(formatTurnover(missing)).toBe('—')
  })

  describe('dataTimeLabel', () => {
    it('shows the clock when the response falls on the data date', () => {
      expect(dataTimeLabel('2026-10-30', '2026-10-30T13:05:00+08:00')).toBe('10/30 13:05')
    })

    it('shows only the date when the clock belongs to a later day', () => {
      expect(dataTimeLabel('2026-10-30', '2026-11-02T03:18:07+08:00')).toBe('10/30')
    })

    it('compares in Taipei time, whatever the viewer or server offset', () => {
      expect(dataTimeLabel('2026-10-30', '2026-10-29T17:30:00Z')).toBe('10/30 01:30')
    })

    it('falls back without inventing a time', () => {
      expect(dataTimeLabel('2026-10-30', 'not-a-date')).toBe('10/30')
      expect(dataTimeLabel('2026-10-30', null)).toBe('10/30')
      expect(dataTimeLabel(null, null)).toBe('—')
    })
  })
})
