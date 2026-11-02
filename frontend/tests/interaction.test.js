/**
 * interaction.test.js — keyboard and form behaviour: dialog focus trap, search
 * navigation, notes, density, theme, breakpoints.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, nextTick, ref } from 'vue'
import { useDialog } from '../src/composables/useDialog'
import { useBreakpoint } from '../src/composables/useBreakpoint'
import GlobalSearch from '../src/components/GlobalSearch.vue'
import DensityControl from '../src/components/DensityControl.vue'
import WatchlistView from '../src/components/WatchlistView.vue'
import WatchAlertsPanel from '../src/components/overview/WatchAlertsPanel.vue'
import { useStockStore } from '../src/stores/stockStore'
import { useWatchlistStore } from '../src/stores/watchlistStore'
import { useUiStore } from '../src/stores/uiStore'
import { useThemeStore } from '../src/stores/themeStore'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

function dialogHarness() {
  const open = ref(false)
  const close = vi.fn(() => { open.value = false })
  const Comp = defineComponent({
    setup() {
      const { dialog } = useDialog(open, close)
      return () => (open.value
        ? h('div', { ref: dialog, tabindex: -1 }, [h('button', { id: 'first' }), h('button', { id: 'last' })])
        : null)
    },
  })
  const opener = document.createElement('button')
  document.body.appendChild(opener)
  const wrapper = mount(Comp, { attachTo: document.body })
  return { open, close, opener, wrapper }
}

const press = (key, shiftKey = false) => {
  const event = new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true })
  document.dispatchEvent(event)
  return event
}

describe('useDialog', () => {
  it('moves focus in on open and back on close', async () => {
    const { open, opener, wrapper } = dialogHarness()
    opener.focus()
    open.value = true
    await nextTick()
    await nextTick()
    expect(document.activeElement).toBe(wrapper.element)
    open.value = false
    await nextTick()
    expect(document.activeElement).toBe(opener)
    wrapper.unmount()
  })

  it('Tab wraps inside the dialog in both directions', async () => {
    const { open, wrapper } = dialogHarness()
    open.value = true
    await nextTick()
    await nextTick()
    const first = wrapper.find('#first').element
    const last = wrapper.find('#last').element

    last.focus()
    expect(press('Tab').defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(first)

    expect(press('Tab', true).defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(last)

    first.focus()
    expect(document.activeElement).toBe(first)
    wrapper.unmount()
  })

  it('Tab in the middle is left to the browser', async () => {
    const { open, wrapper } = dialogHarness()
    open.value = true
    await nextTick()
    await nextTick()
    wrapper.find('#first').element.focus()
    expect(press('Tab').defaultPrevented).toBe(false)
    wrapper.unmount()
  })

  it('Esc closes; other keys do not', async () => {
    const { open, close, wrapper } = dialogHarness()
    open.value = true
    await nextTick()
    press('a')
    expect(close).not.toHaveBeenCalled()
    press('Escape')
    expect(close).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('stops listening once closed or unmounted', async () => {
    const { open, close, wrapper } = dialogHarness()
    open.value = true
    await nextTick()
    wrapper.unmount()
    press('Escape')
    expect(close).not.toHaveBeenCalled()
  })
})

describe('GlobalSearch', () => {
  const pool = [
    { stock_id: '2330', name: '台積電', rank: 1, price_change_pct: 1 },
    { stock_id: '2303', name: '聯電', rank: 3, price_change_pct: -1 },
    { stock_id: '3330', name: '聯積', rank: 2, price_change_pct: 0 },
  ]

  function setup() {
    useStockStore().setData({ sectors: [{ name: '半導體', stocks: pool }] })
    return mount(GlobalSearch, { attachTo: document.body })
  }

  async function type(w, value) {
    const input = w.find('.search-input')
    await input.trigger('focus')
    await input.setValue(value)
    return input
  }

  it('an exact code outranks a name match and a code inside another number', async () => {
    const w = setup()
    await type(w, '2330')
    expect(w.findAll('.item-code').map(c => c.text())).toEqual(['2330'])
    w.unmount()
  })

  it('ranks code prefixes ahead of name matches', async () => {
    const extra = { stock_id: '1234', name: '233測試', rank: 1 }
    useStockStore().setData({ sectors: [{ name: 'X', stocks: [...pool, extra] }] })
    const w = mount(GlobalSearch, { attachTo: document.body })
    await type(w, '233')
    expect(w.findAll('.item-code').map(c => c.text())).toEqual(['2330', '1234'])
    w.unmount()
  })

  it('arrows move the cursor and wrap; Enter opens that stock', async () => {
    const w = setup()
    const input = await type(w, '聯')
    expect(w.findAll('.search-item')[0].classes()).toContain('active')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(w.findAll('.search-item')[1].classes()).toContain('active')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(w.findAll('.search-item')[0].classes()).toContain('active')
    await input.trigger('keydown', { key: 'ArrowUp' })   // wraps to the last result
    await input.trigger('keydown', { key: 'Enter' })
    expect(useUiStore().selectedStockId).toBe('2303')    // 聯積 (rank 2), then 聯電 (rank 3)
    w.unmount()
  })

  it('Enter with no result does nothing', async () => {
    const w = setup()
    const input = await type(w, 'zzz')
    await input.trigger('keydown', { key: 'Enter' })
    expect(useUiStore().selectedStockId).toBe('')
    w.unmount()
  })

  it('Esc clears the query', async () => {
    const w = setup()
    const input = await type(w, '聯')
    await input.trigger('keydown', { key: 'Escape' })
    expect(input.element.value).toBe('')
    w.unmount()
  })

  it('a pointer item opens on click', async () => {
    const w = setup()
    await type(w, '台積')
    await w.find('.search-item').trigger('pointerenter')
    await w.find('.search-item').trigger('click')
    expect(useUiStore().selectedStockId).toBe('2330')
    w.unmount()
  })

  it('finds watchlist stocks outside the display pool', async () => {
    useWatchlistStore().items = [{ stock_id: '6488', quote: { stock_id: '6488', name: '環球晶' } }]
    const w = setup()
    await type(w, '環球')
    expect(w.find('.item-code').text()).toBe('6488')
    w.unmount()
  })

  it('/ focuses search, but not while typing elsewhere', async () => {
    const w = setup()
    const other = document.createElement('input')
    document.body.appendChild(other)
    other.focus()
    other.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }))
    expect(document.activeElement).toBe(other)
    other.blur()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }))
    expect(document.activeElement).toBe(w.find('.search-input').element)
    w.unmount()
  })

  it('clicking away closes the results', async () => {
    const w = setup()
    await type(w, '聯')
    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await nextTick()
    expect(w.find('.search-results').exists()).toBe(false)
    w.unmount()
  })
})

describe('DensityControl', () => {
  it('sets the desktop grid size', async () => {
    const w = mount(DensityControl)
    await w.findAll('button')[2].trigger('click')
    expect(useStockStore().gridSize).toBe(4)
    expect(w.findAll('button')[2].attributes('aria-pressed')).toBe('true')
  })

  it('offers phone densities on a phone', async () => {
    vi.stubGlobal('matchMedia', (query) => ({
      matches: query.includes('max-width: 768px') && !query.includes('min-width'),
      addEventListener: () => {},
      removeEventListener: () => {},
    }))
    const w = mount(DensityControl)
    await nextTick()
    expect(w.findAll('button').map(b => b.text())).toEqual(['2x2', '2x3', '3x3'])
    await w.findAll('button')[0].trigger('click')
    expect(useStockStore().mobileDensity).toBe('2x2')
  })
})

describe('useBreakpoint', () => {
  it('follows media query changes and stops on unmount', async () => {
    const listeners = {}
    const removed = []
    vi.stubGlobal('matchMedia', (query) => ({
      matches: false,
      addEventListener: (_, fn) => { listeners[query] = fn },
      removeEventListener: (_, fn) => removed.push(fn),
    }))
    let state
    const w = mount(defineComponent({
      setup() {
        state = useBreakpoint()
        return () => null
      },
    }))
    const [mobile, tablet] = Object.keys(listeners)
    listeners[mobile]({ matches: true })
    listeners[tablet]({ matches: true })
    expect(state.isMobile.value).toBe(true)
    expect(state.isTablet.value).toBe(true)
    w.unmount()
    expect(removed).toHaveLength(2)
  })
})

describe('themeStore', () => {
  it('toggles, applies and remembers', () => {
    const theme = useThemeStore()
    expect(theme.theme).toBe('dark')
    theme.toggle()
    expect(theme.theme).toBe('light')
  })

  it('starts when storage is blocked', () => {
    const read = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    try {
      setActivePinia(createPinia())
      expect(useThemeStore().theme).toBe('dark')
    } finally {
      read.mockRestore()
      write.mockRestore()
    }
  })
})

describe('WatchlistView — notes and alerts', () => {
  const quote = { stock_id: '2330', name: '台積電', rank: 1, close_price: 80, price_change_pct: -1, color_tier: 'neutral', sector: '半導體' }

  function seed(note = '') {
    const wl = useWatchlistStore()
    wl.items = [{ stock_id: '2330', note, added_at: 'x', quote }]
    wl.loaded = true
    return wl
  }

  it('edits a note and saves on Enter', async () => {
    const wl = seed()
    const save = vi.spyOn(wl, 'saveNote').mockResolvedValue(true)
    const w = mount(WatchlistView)
    await w.find('.watch-note').trigger('click')
    const input = w.find('.watch-note-input')
    await input.setValue('等回測')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(save).toHaveBeenCalledWith('2330', '等回測')
  })

  it('does not save an unchanged note', async () => {
    const wl = seed('原本')
    const save = vi.spyOn(wl, 'saveNote').mockResolvedValue(true)
    const w = mount(WatchlistView)
    await w.find('.watch-note').trigger('click')
    await w.find('.watch-note-input').trigger('blur')
    await flushPromises()
    expect(save).not.toHaveBeenCalled()
    expect(w.find('.watch-note').text()).toBe('原本')
  })

  it('saves once even though Enter blurs the input', async () => {
    const wl = seed()
    const save = vi.spyOn(wl, 'saveNote').mockResolvedValue(true)
    const w = mount(WatchlistView)
    await w.find('.watch-note').trigger('click')
    const input = w.find('.watch-note-input')
    input.element.value = '筆記'
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(save).toHaveBeenCalledOnce()
  })

  it('shows and dismisses an API error', async () => {
    const wl = seed()
    wl.error = '自選股已滿'
    const w = mount(WatchlistView)
    expect(w.find('.watch-error').text()).toContain('自選股已滿')
    await w.find('.watch-error-close').trigger('click')
    expect(wl.error).toBe(null)
  })

  it('shows alerts on the card and opens the panel from the card', async () => {
    seed()
    useStockStore().setSignals({ generated_at: 'g', signals: { 2330: { ma20: 90, ma60: 85 } } })
    const w = mount(WatchlistView)
    expect(w.find('[data-alert="below_ma60"]').text()).toContain('跌破季線')
    await w.find('.stock-cell').trigger('click')
    expect(useUiStore().selectedStockId).toBe('2330')
  })

  it('the overview alert panel lists only stocks with alerts and opens them', async () => {
    const wl = seed()
    wl.items = [...wl.items, { stock_id: '1101', note: '', added_at: 'y', quote: { ...quote, stock_id: '1101', name: '台泥', close_price: 100 } }]
    useStockStore().setSignals({
      generated_at: 'g',
      signals: { 2330: { ma20: 90, ma60: 85 }, 1101: { ma20: 90, ma60: 85 } },
    })
    const w = mount(WatchAlertsPanel)
    expect(w.findAll('.alert-row')).toHaveLength(1)
    await w.find('.alert-row').trigger('click')
    expect(useUiStore().selectedStockId).toBe('2330')
  })

  it('the alert panel hides itself when nothing needs attention', () => {
    seed()
    expect(mount(WatchAlertsPanel).find('.alerts').exists()).toBe(false)
  })
})
