/**
 * WatchlistView.test.js — 自選股視圖 + ScoreDetail 展開明細 + StockCell 釘選
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WatchlistView from '../src/components/WatchlistView.vue'
import ScoreDetail from '../src/components/ScoreDetail.vue'
import StockCell from '../src/components/StockCell.vue'
import { useWatchlistStore } from '../src/stores/watchlistStore'
import { useStockStore } from '../src/stores/stockStore'

const quote = (id, name) => ({
  stock_id: id, name, rank: 3, volume: 1_000_000, turnover_rate: 0.5,
  price_change_pct: 1.2, color_tier: 'light_red', close_price: 100, sector: '半導體',
})

function jsonResponse(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })
}

let fetchMock

beforeEach(() => {
  setActivePinia(createPinia())
  fetchMock = vi.fn(() => jsonResponse({}, 404))
  vi.stubGlobal('fetch', fetchMock)
})

function seed(items) {
  const wl = useWatchlistStore()
  wl.items = items
  wl.loaded = true
  return wl
}

describe('WatchlistView', () => {
  it('shows an empty-state hint when nothing is pinned', () => {
    seed([])
    const w = mount(WatchlistView)
    expect(w.find('.watchlist-empty').text()).toContain('☆')
  })

  it('renders one card per item with its note', () => {
    seed([
      { stock_id: '2330', note: '等回測月線', added_at: 'x', quote: quote('2330', '台積電') },
      { stock_id: '2317', note: '', added_at: 'y', quote: quote('2317', '鴻海') },
    ])
    const w = mount(WatchlistView)
    expect(w.findAll('.watch-card')).toHaveLength(2)
    expect(w.findAll('.cell-name-text').map(n => n.text())).toEqual(['台積電', '鴻海'])
    expect(w.find('.watch-note').text()).toContain('等回測月線')
  })

  it('passes buy score to the card (watchlist mode tints by signal)', () => {
    seed([{ stock_id: '2330', note: '', added_at: 'x', quote: quote('2330', '台積電') }])
    const stock = useStockStore()
    stock.setScores({ '2330': { score: 18, max_score: 24, pass_rate: 78.3, signal: 'strong_buy', signal_label: '建議買進' } })
    const w = mount(WatchlistView)
    expect(w.find('.stock-cell').attributes('data-signal')).toBe('strong_buy')
    expect(w.find('.cell-passrate').text()).toBe('78%')
  })

  it('shows a placeholder when the quote is missing', () => {
    seed([{ stock_id: '1234', note: '', added_at: 'x', quote: null }])
    const w = mount(WatchlistView)
    expect(w.find('.watch-noquote').text()).toContain('1234')
  })

  it('remove button unpins', async () => {
    const wl = seed([{ stock_id: '2330', note: '', added_at: 'x', quote: quote('2330', '台積電') }])
    const spy = vi.spyOn(wl, 'unpin').mockResolvedValue(true)
    const w = mount(WatchlistView)
    await w.find('.watch-remove').trigger('click')
    expect(spy).toHaveBeenCalledWith('2330')
  })

  it('expand toggles the score detail panel', async () => {
    seed([{ stock_id: '2330', note: '', added_at: 'x', quote: quote('2330', '台積電') }])
    const w = mount(WatchlistView)
    expect(w.findComponent(ScoreDetail).exists()).toBe(false)
    await w.find('.watch-expand').trigger('click')
    expect(w.findComponent(ScoreDetail).exists()).toBe(true)
  })
})

describe('ScoreDetail', () => {
  it('lists passed / failed / missing criteria and risk items', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({
      date: '2026-10-01', stock_id: '2330',
      criteria: [
        { id: 'roe', label: 'ROE (TTM) > 12%', pass: true, value_label: '28.1%' },
        { id: 'debt_ratio', label: '負債比 < 60%', pass: false, value_label: '65%' },
        { id: 'pe_p25', label: 'P/E < p25', pass: null, value_label: '無資料' },
      ],
      risk_criteria: [{ category: '獲利排雷', name: '自由現金流轉負', value_label: 'FCF = -1', description: '...' }],
    }))
    const w = mount(ScoreDetail, { props: { stockId: '2330' } })
    await flushPromises()
    expect(fetchMock.mock.calls[0][0]).toContain('/api/scores/2330')
    expect(w.findAll('.crit--pass')).toHaveLength(1)
    expect(w.findAll('.crit--fail')).toHaveLength(1)
    expect(w.findAll('.crit--na')).toHaveLength(1)
    expect(w.find('.risk-item').text()).toContain('自由現金流轉負')
  })

  it('shows 尚未評分 on 404', async () => {
    fetchMock.mockReturnValueOnce(jsonResponse({ detail: 'nf' }, 404))
    const w = mount(ScoreDetail, { props: { stockId: '6488' } })
    await flushPromises()
    expect(w.text()).toContain('尚未評分')
  })
})

describe('StockCell — pin toggle', () => {
  const stock = { stock_id: '2330', name: '台積電', rank: 1, color_tier: 'neutral', sector: '半導體' }

  it('hidden unless pinnable', () => {
    const w = mount(StockCell, { props: { stock } })
    expect(w.find('.cell-pin').exists()).toBe(false)
  })

  it('shows ☆ when not pinned and emits toggle-pin on click', async () => {
    const w = mount(StockCell, { props: { stock, pinnable: true, pinned: false } })
    expect(w.find('.cell-pin').text()).toBe('☆')
    await w.find('.cell-pin').trigger('click')
    expect(w.emitted('toggle-pin')[0]).toEqual(['2330'])
  })

  it('shows ★ when pinned', () => {
    const w = mount(StockCell, { props: { stock, pinnable: true, pinned: true } })
    expect(w.find('.cell-pin').text()).toBe('★')
    expect(w.find('.cell-pin').classes()).toContain('is-pinned')
  })
})
