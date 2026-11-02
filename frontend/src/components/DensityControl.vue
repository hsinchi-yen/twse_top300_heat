<template>
  <div class="segmented density-control" role="group" aria-label="每頁卡片數">
    <button
      v-for="option in options"
      :key="option.value"
      class="segmented__item"
      :class="{ active: option.active }"
      :aria-pressed="option.active"
      @click="option.select"
    >{{ option.value }}</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useBreakpoint } from '../composables/useBreakpoint'
import { MOBILE_DENSITY } from '../constants'

const store = useStockStore()
const { gridSize, mobileDensity } = storeToRefs(store)
const { isMobile } = useBreakpoint()

const options = computed(() => (isMobile.value
  ? Object.keys(MOBILE_DENSITY).map(d => ({
      value: d, active: mobileDensity.value === d, select: () => store.setMobileDensity(d),
    }))
  : [6, 5, 4].map(n => ({
      value: `${n}×${n}`, active: gridSize.value === n, select: () => store.setGridSize(n),
    }))))
</script>
