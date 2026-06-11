import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref(localStorage.getItem('theme') ?? 'dark')

  watch(theme, t => {
    document.documentElement.dataset.theme = t === 'light' ? 'light' : ''
    localStorage.setItem('theme', t)
  }, { immediate: true })

  const toggle = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return { theme, toggle }
})
