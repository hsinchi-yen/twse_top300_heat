/**
 * charts.test.js — scale math plus the behaviours a chart must keep: gaps stay
 * gaps, a table twin exists, the same readout works on hover and keyboard.
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import LineChart from '../src/components/charts/LineChart.vue'
import ColumnChart from '../src/components/charts/ColumnChart.vue'
import { extent, linePath, niceTicks, slotIndex, tickIndexes } from '../src/utils/chartScale'

describe('chartScale', () => {
  it('extent skips nulls across series', () => {
    expect(extent([[1, null, 5], [null, -2]])).toEqual([-2, 5])
    expect(extent([[null]])).toBe(null)
  })

  it('niceTicks bracket the data with round steps', () => {
    const ticks = niceTicks(103, 187)
    expect(ticks[0]).toBeLessThanOrEqual(103)
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(187)
    expect(ticks.every(t => Number.isInteger(t / 20) || Number.isInteger(t / 25))).toBe(true)
  })

  it('niceTicks survive a flat series', () => {
    expect(niceTicks(100, 100).length).toBeGreaterThan(1)
    expect(niceTicks(0, 0).length).toBeGreaterThan(1)
  })

  it('niceTicks handle small decimals without float dust', () => {
    for (const t of niceTicks(0.1, 0.34)) expect(String(t).length).toBeLessThan(6)
  })

  it('niceTicks reject missing input', () => {
    expect(niceTicks(null, 1)).toEqual([])
  })

  it('linePath lifts the pen over gaps instead of interpolating', () => {
    const d = linePath([{ x: 0, y: 0 }, { x: 1, y: 1 }, null, { x: 3, y: 3 }])
    expect(d).toBe('M0.0 0.0L1.0 1.0M3.0 3.0')
  })

  it('slotIndex clamps to the data range', () => {
    expect(slotIndex(-10, 0, 100, 11)).toBe(0)
    expect(slotIndex(50, 0, 100, 11)).toBe(5)
    expect(slotIndex(999, 0, 100, 11)).toBe(10)
    expect(slotIndex(5, 0, 100, 1)).toBe(0)
  })

  it('tickIndexes include both ends', () => {
    expect(tickIndexes(100, 4)).toEqual([0, 33, 66, 99])
    expect(tickIndexes(2, 4)).toEqual([0, 1])
    expect(tickIndexes(0)).toEqual([])
  })
})

const dates = ['2026-01-01', '2026-01-02', '2026-01-03', '2026-01-04']
const series = [
  { key: 'close', label: '收盤', color: 'var(--series-1)', values: [10, 11, 12, 13] },
  { key: 'ma20', label: '月線', color: 'var(--series-2)', values: [null, null, 11, 12] },
]

describe('LineChart', () => {
  it('has a legend carrying the latest value for two or more series', () => {
    const w = mount(LineChart, { props: { dates, series } })
    expect(w.find('.chart-legend').text()).toContain('收盤')
    expect(w.find('.chart-legend').text()).toContain('13')
  })

  it('omits the legend for one series', () => {
    const w = mount(LineChart, { props: { dates, series: series.slice(0, 1) } })
    expect(w.find('.chart-legend').exists()).toBe(false)
  })

  it('draws one path per series and never bridges leading nulls', () => {
    const w = mount(LineChart, { props: { dates, series } })
    expect(w.findAll('path.line')).toHaveLength(2)
    expect(w.find('path.line--ma20').attributes('d')).toMatch(/^M/)
    expect((w.find('path.line--ma20').attributes('d').match(/L/g) ?? []).length).toBe(1)
  })

  it('offers a table twin, newest first', () => {
    const w = mount(LineChart, { props: { dates, series } })
    const rows = w.findAll('.chart-data tbody tr')
    expect(rows).toHaveLength(4)
    expect(rows[0].text()).toContain('2026-01-04')
    expect(rows[3].text()).toContain('—')
  })

  it('names itself for assistive tech', () => {
    const w = mount(LineChart, { props: { dates, series, title: '價格' } })
    expect(w.find('.chart-plot').attributes('aria-label')).toContain('價格')
    expect(w.find('.chart-plot').attributes('aria-label')).toContain('收盤 13')
  })

  it('keyboard focus shows the same readout as hover and arrows step days', async () => {
    const w = mount(LineChart, { props: { dates, series } })
    const plot = w.find('.chart-plot')
    await plot.trigger('focus')
    expect(w.find('.chart-tip').text()).toContain('2026-01-04')
    await plot.trigger('keydown', { key: 'ArrowLeft' })
    expect(w.find('.chart-tip').text()).toContain('2026-01-03')
    await plot.trigger('keydown', { key: 'ArrowRight' })
    await plot.trigger('keydown', { key: 'ArrowRight' })
    expect(w.find('.chart-tip').text()).toContain('2026-01-04')
    await plot.trigger('blur')
    expect(w.find('.chart-tip').exists()).toBe(false)
  })

  it('pointer position selects the nearest date', async () => {
    const w = mount(LineChart, { props: { dates, series } })
    const move = new MouseEvent('pointermove', { clientX: 2, bubbles: true })
    w.find('.chart-plot').element.dispatchEvent(move)
    await nextTick()
    expect(w.find('.chart-tip').text()).toContain('2026-01-01')
  })

  it('resets the readout when the date range changes', async () => {
    const w = mount(LineChart, { props: { dates, series } })
    await w.find('.chart-plot').trigger('focus')
    await w.setProps({ dates: dates.slice(0, 2), series: series.map(s => ({ ...s, values: s.values.slice(0, 2) })) })
    await nextTick()
    expect(w.find('.chart-tip').exists()).toBe(false)
  })

  it('area wash only on request', () => {
    expect(mount(LineChart, { props: { dates, series } }).find('path.area').exists()).toBe(false)
    const one = series.slice(0, 1)
    expect(mount(LineChart, { props: { dates, series: one, area: true } }).find('path.area').exists()).toBe(true)
  })
})

describe('ColumnChart', () => {
  const values = [100, -50, 0, null]

  it('draws a bar per non-zero value', () => {
    const w = mount(ColumnChart, { props: { dates, values, label: '買賣超' } })
    expect(w.findAll('path.column')).toHaveLength(2)
  })

  it('direction tone uses Taiwan colours: buy red, sell green', () => {
    const w = mount(ColumnChart, { props: { dates, values, label: '買賣超', tone: 'direction' } })
    const fills = w.findAll('path.column').map(b => b.attributes('fill'))
    expect(fills).toEqual(['var(--pct-up)', 'var(--pct-down)'])
  })

  it('neutral tone uses one colour', () => {
    const w = mount(ColumnChart, { props: { dates, values: [1, 2], label: '量' } })
    expect(new Set(w.findAll('path.column').map(b => b.attributes('fill'))).size).toBe(1)
  })

  it('always includes the zero baseline', () => {
    const w = mount(ColumnChart, { props: { dates: dates.slice(0, 2), values: [100, 120], label: '量' } })
    expect(w.findAll('.axis-text').some(t => t.text() === '0')).toBe(true)
  })

  it('caps bar width at 24px however few bars there are', () => {
    const w = mount(ColumnChart, { props: { dates: dates.slice(0, 1), values: [100], label: '量' } })
    const d = w.find('path.column').attributes('d')
    const left = Number(d.match(/^M([\d.]+)/)[1])
    const right = Math.max(...[...d.matchAll(/Q([\d.]+)/g)].map(m => Number(m[1])))
    expect(right - left).toBeGreaterThan(0)
    expect(right - left).toBeLessThanOrEqual(24.01)
  })

  it('has the keyboard readout and a table twin', async () => {
    const w = mount(ColumnChart, { props: { dates, values: [1, 2, 3, 4], label: '量' } })
    await w.find('.chart-plot').trigger('focus')
    expect(w.find('.chart-tip').text()).toContain('2026-01-04')
    await w.find('.chart-plot').trigger('keydown', { key: 'ArrowLeft' })
    expect(w.find('.chart-tip').text()).toContain('2026-01-03')
    expect(w.findAll('.chart-data tbody tr')).toHaveLength(4)
  })
})
