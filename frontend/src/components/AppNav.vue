<template>
  <nav class="app-nav" aria-label="主要視圖">
    <button
      v-for="tab in tabs"
      :id="`nav-${tab.key}`"
      :key="tab.key"
      class="nav-tab"
      :class="{ active: tab.active }"
      :aria-current="tab.active ? 'page' : undefined"
      @click="emit('mode-change', tab.target)"
    >
      <Icon :name="tab.icon" :size="16" />
      <span>{{ tab.label }}</span>
      <span v-if="tab.count" class="nav-count num">{{ tab.count }}</span>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { HEATMAP_MODES } from '../stores/stockStore'
import Icon from './Icon.vue'

const props = defineProps({
  mode:        { type: String, required: true },
  heatmapMode: { type: String, default: 'turnover' },
  watchCount:  { type: Number, default: 0 },
})
const emit = defineEmits(['mode-change'])

const tabs = computed(() => [
  { key: 'overview', label: '總覽', icon: 'overview', target: 'overview', active: props.mode === 'overview' },
  { key: 'heatmap', label: '熱力圖', icon: 'grid', target: props.heatmapMode, active: HEATMAP_MODES.includes(props.mode) },
  { key: 'etf', label: 'ETF', icon: 'layers', target: 'etf', active: props.mode === 'etf' },
  { key: 'watchlist', label: '自選', icon: 'star', target: 'watchlist', active: props.mode === 'watchlist', count: props.watchCount },
])
</script>

<style scoped>
.app-nav {
  display: flex;
  gap: 2px;
}

.nav-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.12s, color 0.12s;
}
.nav-tab:hover { background: var(--hover-wash); color: var(--text-primary); }
.nav-tab.active { background: var(--accent-soft); color: var(--accent); font-weight: 600; }

.nav-count {
  font-size: 0.75rem;
  font-weight: 600;
  opacity: 0.8;
}

@media (max-width: 768px) {
  .app-nav {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 200;
    justify-content: space-around;
    padding: 4px 8px calc(4px + env(safe-area-inset-bottom));
    background: var(--surface);
    border-top: 1px solid var(--border-subtle);
  }
  .nav-tab {
    flex: 1;
    flex-direction: column;
    justify-content: center;
    gap: 1px;
    min-height: 48px;
    padding: 0 4px;
    font-size: 0.75rem;
  }
  .nav-tab.active { background: transparent; }
  .nav-count { display: none; }
}
</style>
