import { ref, onMounted, onUnmounted } from 'vue'

const MOBILE_QUERY = '(max-width: 768px)'

// Reactive isMobile flag driven by matchMedia.
// Guards against environments without matchMedia (e.g. jsdom in tests),
// where it defaults to desktop (false).
export function useBreakpoint() {
  const isMobile = ref(false)
  let mql = null

  function update(e) {
    isMobile.value = e.matches
  }

  onMounted(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    mql = window.matchMedia(MOBILE_QUERY)
    isMobile.value = mql.matches
    mql.addEventListener('change', update)
  })

  onUnmounted(() => {
    if (mql) mql.removeEventListener('change', update)
  })

  return { isMobile }
}
