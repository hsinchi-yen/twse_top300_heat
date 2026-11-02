/** useChartWidth.js — tracks a chart container's width so text never gets stretched. */

import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useChartWidth(fallback = 560) {
  const root = ref(null)
  const width = ref(fallback)
  let observer = null

  function measure() {
    const w = root.value?.clientWidth
    if (w) width.value = w
  }

  onMounted(() => {
    measure()
    if (typeof ResizeObserver !== 'undefined' && root.value) {
      observer = new ResizeObserver(measure)
      observer.observe(root.value)
    }
  })
  onBeforeUnmount(() => observer?.disconnect())

  return { root, width }
}
