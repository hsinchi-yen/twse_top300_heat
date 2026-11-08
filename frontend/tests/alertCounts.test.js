import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BreadthPanel from '../src/components/overview/BreadthPanel.vue'
import { useMarketStore } from '../src/stores/marketStore'

const SUMMARY = { scored: 0, signalCounts: {} }

describe('alert-count history', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('stays hidden until two scoring dates exist', () => {
    const market = useMarketStore()
    market.trendLoaded = true
    market.alertCounts = { date: '2026-11-06', summary: [{ date: '2026-11-06', median: 40 }], alerts: [] }
    const w = mount(BreadthPanel, { props: { summary: SUMMARY } })
    expect(w.text()).not.toContain('千張大戶退場')
  })

  it('plots the median and the whale-exit share', () => {
    const market = useMarketStore()
    market.trendLoaded = true
    market.alertCounts = {
      date: '2026-11-06',
      summary: [{ date: '2026-11-05', median: 42 }, { date: '2026-11-06', median: 40 }],
      alerts: [{ name: '千張大戶退場', counts: [10, 30], shares: [2.0, 6.0] }],
    }
    const w = mount(BreadthPanel, { props: { summary: SUMMARY } })
    expect(w.text()).toContain('千張大戶退場')
    expect(w.text()).toContain('6%')
  })

  it('a failed request keeps the last payload', async () => {
    const market = useMarketStore()
    market.alertCounts = { date: 'x', summary: [], alerts: [] }
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 })
    await market.loadAlertCounts()
    expect(market.alertCounts.date).toBe('x')
  })
})
