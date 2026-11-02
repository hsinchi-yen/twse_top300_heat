/** uiStore.js — transient UI state: which stock panel / guide is open. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const selectedStockId = ref('')
  const guideOpen = ref(false)
  const settingsOpen = ref(false)

  function openStock(stockId) {
    selectedStockId.value = stockId
  }

  function closeStock() {
    selectedStockId.value = ''
  }

  function openGuide() {
    guideOpen.value = true
  }

  function closeGuide() {
    guideOpen.value = false
  }

  function openSettings() {
    settingsOpen.value = true
  }

  function closeSettings() {
    settingsOpen.value = false
  }

  return {
    selectedStockId, guideOpen, settingsOpen,
    openStock, closeStock, openGuide, closeGuide, openSettings, closeSettings,
  }
})
