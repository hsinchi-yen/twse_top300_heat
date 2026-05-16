<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-left">
        <h1 class="app-title">🇹🇼 台股熱力圖</h1>
        <ModeToggle :mode="mode" @mode-change="onModeChange" />
      </div>
      <div class="topbar-right">
        <span v-if="!marketOpen" class="badge badge-closed">📴 今日已收盤</span>
        <span v-else class="badge badge-open">🟢 盤中</span>
        <span class="last-updated">
          最後更新：{{ formattedTime }}
        </span>
      </div>
    </header>

    <main class="main-content">
      <HeatmapGrid />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from './stores/stockStore'
import { useStockData } from './composables/useStockData'
import ModeToggle from './components/ModeToggle.vue'
import HeatmapGrid from './components/HeatmapGrid.vue'

const store = useStockStore()
const { mode, marketOpen, updatedAt } = storeToRefs(store)

useStockData()

function onModeChange(newMode) {
  store.setMode(newMode)
}

const formattedTime = computed(() => {
  if (!updatedAt.value) return '—'
  return new Date(updatedAt.value).toLocaleTimeString('zh-TW', { hour12: false })
})
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0d0d0d;
  color: #e0e0e0;
  font-family: 'Inter', 'Noto Sans TC', sans-serif;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
  background: #111;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.app-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #fff;
  margin: 0;
  letter-spacing: 0.05em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.badge {
  font-size: 0.78rem;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-weight: 600;
}

.badge-open   { background: #1b3a1b; color: #69f069; }
.badge-closed { background: #3a1b1b; color: #f06969; }

.last-updated {
  font-size: 0.75rem;
  color: #666;
}

.main-content {
  flex: 1;
  padding: 1rem 1.5rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
