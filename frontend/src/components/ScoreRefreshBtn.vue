<template>
  <button
    v-if="hasToken"
    class="score-refresh-btn"
    :class="{ spinning: scoresFetching }"
    :disabled="scoresFetching"
    :title="scoresFetching ? '評分更新中…' : '重新抓取買入評分'"
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
import { forceRefreshScores, getStoredToken } from '../composables/useScoreData'

const store = useStockStore()
const { scoresFetching } = storeToRefs(store)

const hasToken = computed(() => !!getStoredToken())

function onClick() {
  if (!scoresFetching.value) {
    forceRefreshScores()
  }
}
</script>

<style scoped>
.score-refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  background: rgba(0, 229, 255, 0.06);
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-radius: 5px;
  color: rgba(0, 229, 255, 0.55);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  flex-shrink: 0;
}

.score-refresh-btn:hover:not(:disabled) {
  background: rgba(0, 229, 255, 0.12);
  border-color: rgba(0, 229, 255, 0.45);
  color: #00e5ff;
}

.score-refresh-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.icon {
  width: 14px;
  height: 14px;
}

.spinning .icon {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

@media (max-width: 1366px), (max-height: 768px) {
  .score-refresh-btn {
    width: 24px;
    height: 24px;
  }
  .icon {
    width: 12px;
    height: 12px;
  }
}
</style>
