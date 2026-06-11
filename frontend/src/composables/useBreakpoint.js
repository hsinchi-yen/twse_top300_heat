import { ref, onMounted, onUnmounted } from 'vue'

const MOBILE_QUERY  = '(max-width: 768px)'
const TABLET_QUERY  = '(min-width: 769px) and (max-width: 1024px)'

export function useBreakpoint() {
  const isMobile = ref(false)
  const isTablet = ref(false)
  let mqlMobile = null
  let mqlTablet = null

  function updateMobile(e) { isMobile.value = e.matches }
  function updateTablet(e) { isTablet.value = e.matches }

  onMounted(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    mqlMobile = window.matchMedia(MOBILE_QUERY)
    mqlTablet = window.matchMedia(TABLET_QUERY)
    isMobile.value = mqlMobile.matches
    isTablet.value = mqlTablet.matches
    mqlMobile.addEventListener('change', updateMobile)
    mqlTablet.addEventListener('change', updateTablet)
  })

  onUnmounted(() => {
    if (mqlMobile) mqlMobile.removeEventListener('change', updateMobile)
    if (mqlTablet) mqlTablet.removeEventListener('change', updateTablet)
  })

  return { isMobile, isTablet }
}
