<template>
  <button
    class="icon-btn score-refresh-btn"
    :class="{ spinning: scoresFetching && !scoresStalled }"
    :disabled="scoresFetching && !scoresStalled"
    :title="btnTitle"
    :aria-label="btnTitle"
    @click="onClick"
  >
    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
    </svg>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { forceRefreshScores } from '../composables/useScoreData'

const store = useStockStore()
const { scoresFetching, scoresStalled } = storeToRefs(store)

const btnTitle = computed(() => {
  if (scoresStalled.value) return '評分似乎停滯，點擊重試'
  if (scoresFetching.value) return '評分更新中…'
  return '重新計算買進評分（約 90 分鐘）'
})

// Allow a click when idle, or when a background fetch appears stalled (the
// backend stale-flag timeout lets a fresh force refresh take over).
function onClick() {
  if (!scoresFetching.value || scoresStalled.value) {
    forceRefreshScores()
  }
}
</script>

<style scoped>
.icon {
  width: 16px;
  height: 16px;
}

.spinning .icon {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
