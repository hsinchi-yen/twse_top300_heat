import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SettingsModal from '../src/components/SettingsModal.vue'
import { useUiStore } from '../src/stores/uiStore'

const TOKEN = 'eyJhbGciOiJIUzI1NiJ9.secretvalue1234'

function stubApi(initial = { configured: false, hint: null }) {
  let state = initial
  const calls = []
  vi.stubGlobal('fetch', vi.fn(async (url, opts = {}) => {
    const method = opts.method || 'GET'
    calls.push({ url, method, body: opts.body })
    if (method === 'PUT') {
      const t = JSON.parse(opts.body).token
      if (/\s/.test(t)) return { ok: false, status: 422, json: async () => ({}) }
      state = { configured: true, hint: '****1234' }
    }
    if (method === 'DELETE') state = { configured: false, hint: null }
    return { ok: true, status: 200, json: async () => state }
  }))
  return calls
}

async function open() {
  const ui = useUiStore()
  const w = mount(SettingsModal, { attachTo: document.body })
  ui.openSettings()
  await flushPromises()
  return { w, ui }
}

beforeEach(() => { setActivePinia(createPinia()); localStorage.clear() })
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = '' })

describe('SettingsModal — FinMind token', () => {
  it('shows not-configured state with a password input', async () => {
    stubApi()
    const { w } = await open()
    expect(w.text()).toContain('未設定')
    expect(w.find('input[type="password"]').exists()).toBe(true)
  })

  it('is not rendered while closed', () => {
    stubApi()
    const w = mount(SettingsModal)
    expect(w.find('[role="dialog"]').exists()).toBe(false)
  })

  it('saves via PUT, clears the input, never persists the token in the browser', async () => {
    const calls = stubApi()
    const { w } = await open()
    await w.find('input').setValue(`  ${TOKEN} `)
    await w.find('form').trigger('submit')
    await flushPromises()
    const put = calls.find(c => c.method === 'PUT')
    expect(put.url).toContain('/api/settings/finmind-token')
    expect(JSON.parse(put.body)).toEqual({ token: TOKEN })
    expect(w.find('input').element.value).toBe('')
    expect(w.text()).toContain('已設定')
    expect(w.text()).toContain('****1234')
    expect(w.text()).not.toContain(TOKEN)
    expect(JSON.stringify({ ...localStorage })).not.toContain('secretvalue')
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('secretvalue')
  })

  it('does not submit an empty token', async () => {
    const calls = stubApi()
    const { w } = await open()
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(calls.some(c => c.method === 'PUT')).toBe(false)
  })

  it('shows a validation error for a rejected token', async () => {
    stubApi()
    const { w } = await open()
    await w.find('input').setValue('has space')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('格式')
  })

  it('removes the token via DELETE', async () => {
    const calls = stubApi({ configured: true, hint: '****1234' })
    const { w } = await open()
    await w.find('button.btn-clear').trigger('click')
    await flushPromises()
    expect(calls.some(c => c.method === 'DELETE')).toBe(true)
    expect(w.text()).toContain('未設定')
  })
})
