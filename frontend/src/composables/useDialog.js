/**
 * useDialog.js — modal behaviour shared by the stock panel and the guide:
 * focus moves in on open and returns on close, Tab stays inside, Esc closes.
 */

import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'

export function useDialog(isOpen, close) {
  const dialog = ref(null)
  let returnTo = null

  function onKey(e) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      close()
      return
    }
    if (e.key !== 'Tab' || !dialog.value) return
    const items = [...dialog.value.querySelectorAll(FOCUSABLE)]
    if (!items.length) return
    const first = items[0]
    const last = items[items.length - 1]
    const current = document.activeElement
    if (e.shiftKey && current === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && current === last) {
      e.preventDefault()
      first.focus()
    }
  }

  watch(isOpen, async (open) => {
    if (open) {
      returnTo = document.activeElement
      document.addEventListener('keydown', onKey)
      await nextTick()
      dialog.value?.focus()
    } else {
      document.removeEventListener('keydown', onKey)
      if (returnTo instanceof HTMLElement) returnTo.focus()
      returnTo = null
    }
  }, { immediate: true })

  onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

  return { dialog }
}
