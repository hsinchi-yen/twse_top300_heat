/**
 * TokenSettings.test.js — TDD tests for FinMind token localStorage UI
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TokenSettings from '../src/components/TokenSettings.vue'

// Mock fetchScores so save/clear don't make real network calls
vi.mock('../src/composables/useScoreData', () => ({
  fetchScores: vi.fn(),
}))

const STORAGE_KEY = 'finmind_token'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

function mountWidget() {
  return mount(TokenSettings, { attachTo: document.body })
}

describe('TokenSettings — initial state', () => {
  it('renders the key button', () => {
    const w = mountWidget()
    expect(w.find('.token-btn').exists()).toBe(true)
  })

  it('panel is closed by default', () => {
    const w = mountWidget()
    expect(w.find('.token-panel').exists()).toBe(false)
  })

  it('button has no "token-set" class when no token stored', () => {
    const w = mountWidget()
    expect(w.find('.token-btn').classes()).not.toContain('token-set')
  })

  it('button has "token-set" class when token exists in localStorage', () => {
    localStorage.setItem(STORAGE_KEY, 'test-token-abc')
    const w = mountWidget()
    expect(w.find('.token-btn').classes()).toContain('token-set')
  })
})

describe('TokenSettings — open/close panel', () => {
  it('opens panel on button click', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    expect(w.find('.token-panel').exists()).toBe(true)
  })

  it('closes panel on second button click', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.token-btn').trigger('click')
    expect(w.find('.token-panel').exists()).toBe(false)
  })

  it('shows close button inside panel', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    expect(w.find('.btn-close').exists()).toBe(true)
  })

  it('close button hides panel', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.btn-close').trigger('click')
    expect(w.find('.token-panel').exists()).toBe(false)
  })
})

describe('TokenSettings — save token', () => {
  it('saves token to localStorage on save', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.token-input').setValue('my-secret-token')
    await w.find('.btn-save').trigger('click')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('my-secret-token')
  })

  it('closes panel after saving', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.token-input').setValue('my-token')
    await w.find('.btn-save').trigger('click')
    expect(w.find('.token-panel').exists()).toBe(false)
  })

  it('does not save empty string', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.token-input').setValue('   ')
    await w.find('.btn-save').trigger('click')
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('button gains token-set class after saving', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.token-input').setValue('saved-token')
    await w.find('.btn-save').trigger('click')
    expect(w.find('.token-btn').classes()).toContain('token-set')
  })
})

describe('TokenSettings — clear token', () => {
  it('shows clear button when token is set', async () => {
    localStorage.setItem(STORAGE_KEY, 'existing-token')
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    expect(w.find('.btn-clear').exists()).toBe(true)
  })

  it('does not show clear button when no token', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    expect(w.find('.btn-clear').exists()).toBe(false)
  })

  it('removes token from localStorage on clear', async () => {
    localStorage.setItem(STORAGE_KEY, 'existing-token')
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.btn-clear').trigger('click')
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('button loses token-set class after clear', async () => {
    localStorage.setItem(STORAGE_KEY, 'existing-token')
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    await w.find('.btn-clear').trigger('click')
    expect(w.find('.token-btn').classes()).not.toContain('token-set')
  })
})

describe('TokenSettings — masked display', () => {
  it('shows masked token when set', async () => {
    localStorage.setItem(STORAGE_KEY, 'eyJhbGciTest1234')
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    const status = w.find('.token-status').text()
    expect(status).toContain('eyJhbGci')
    expect(status).not.toBe('eyJhbGciTest1234')
  })

  it('shows "未設定" when no token', async () => {
    const w = mountWidget()
    await w.find('.token-btn').trigger('click')
    expect(w.find('.token-status').text()).toContain('未設定')
  })
})
