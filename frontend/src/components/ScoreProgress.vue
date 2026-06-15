<template>
  <span class="score-progress mono">
    <template v-if="scoresFetching">
      <span class="sp-bar" :title="`計分中 ${scoredCount} / ${totalCount}`">
        <span class="sp-bar-fill" :style="{ width: pct + '%' }" />
      </span>
      <span class="sp-text">{{ scoredCount }}/{{ totalCount }}（{{ pct }}%）</span>
    </template>
    <span v-else-if="lastUpdatedLabel" class="sp-text sp-done" :title="`評分更新 ${lastUpdatedLabel}`">
      評分更新 {{ lastUpdatedLabel }}
    </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'

const store = useStockStore()
const { sectors, scores, scoresFetching, scoreDate, scoreGeneratedAt, scoreProgress } = storeToRefs(store)

// Counting scored stocks only works on a cold start; during a force refresh the
// merged JSON keeps the full baseline, so prefer the crawler's real recompute
// counter (scoreProgress) when the backend reports it.
const totalCount = computed(() => {
  if (scoreProgress.value) return scoreProgress.value.total
  let n = 0
  for (const sector of sectors.value) n += (sector.stocks?.length ?? 0)
  return n
})

const scoredCount = computed(() => {
  if (scoreProgress.value) return scoreProgress.value.done
  const sc = scores.value
  let n = 0
  for (const sector of sectors.value) {
    for (const s of sector.stocks ?? []) {
      const e = sc[s.stock_id]
      if (e && e.score != null && e.max_score !== 0) n++
    }
  }
  return n
})

const pct = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.min(100, Math.round((scoredCount.value / totalCount.value) * 100))
})

// "2026-06-01 03:42" — prefers generated_at (has time); falls back to date.
const lastUpdatedLabel = computed(() => {
  const gen = scoreGeneratedAt.value
  if (gen) {
    const d = new Date(gen)
    if (!isNaN(d.getTime())) {
      const date = d.toLocaleDateString('sv-SE')
      const time = d.toLocaleTimeString('zh-TW', { hour12: false, hour: '2-digit', minute: '2-digit' })
      return `${date} ${time}`
    }
  }
  return scoreDate.value || ''
})
</script>

<style scoped>
.score-progress {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.68rem;
  color: var(--last-updated-color);
  letter-spacing: 0.03em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  white-space: nowrap;
}

.sp-bar {
  position: relative;
  width: 72px;
  height: 6px;
  border-radius: 3px;
  background: var(--ctrl-dot-bg, rgba(127, 127, 127, 0.25));
  overflow: hidden;
}

.sp-bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  height: 100%;
  background: linear-gradient(90deg, var(--title-from, #4caf50), var(--title-to, #2196f3));
  border-radius: 3px;
  transition: width 0.4s ease;
}

.sp-text { font-variant-numeric: tabular-nums; }
.sp-done { opacity: 0.85; }

@media (max-width: 1366px), (max-height: 768px) {
  .score-progress { font-size: 0.62rem; }
  .sp-bar { width: 56px; }
}

/* 手機直屏：只留進度條，省空間 */
@media (max-width: 640px) {
  .sp-done { display: none; }
  .sp-bar { width: 44px; }
}
</style>
