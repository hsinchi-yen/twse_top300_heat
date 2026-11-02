import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// Per-viewer convenience: blocked storage must never stop the app from starting.
function storedTheme() {
  try {
    return localStorage.getItem('theme') === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref(storedTheme())

  watch(theme, t => {
    document.documentElement.dataset.theme = t === 'light' ? 'light' : ''
    try {
      localStorage.setItem('theme', t)
    } catch {
      // storage unavailable — the theme still applies for this session
    }
  }, { immediate: true })

  const toggle = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return { theme, toggle }
})
