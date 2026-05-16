<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-left">
        <h1 class="app-title">
          <span class="title-flag">🇹🇼</span>
          <span class="title-text">台股熱力圖</span>
        </h1>
        <ModeToggle :mode="mode" @mode-change="onModeChange" />
      </div>
      <div class="topbar-right">
        <!-- 資料日期（非今日時顯示） -->
        <span v-if="dataDate && dataDate !== todayStr" class="badge badge-date">
          📅 {{ dataDate }}
        </span>
        <span v-if="!marketOpen" class="badge badge-closed">◼ 已收盤</span>
        <span v-else class="badge badge-open">● 盤中</span>
        <span class="last-updated mono">{{ formattedTime }}</span>
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
const { mode, marketOpen, updatedAt, date: dataDate } = storeToRefs(store)

useStockData()

function onModeChange(newMode) {
  store.setMode(newMode)
}

const todayStr = new Date().toLocaleDateString('sv-SE')  // "2026-05-16"

const formattedTime = computed(() => {
  if (!updatedAt.value) return '— : — : —'
  return new Date(updatedAt.value).toLocaleTimeString('zh-TW', { hour12: false })
})
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: transparent;
  color: #c8d8e8;
  font-family: 'Inter', 'Noto Sans TC', sans-serif;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 1.5rem;
  background: rgba(5, 8, 16, 0.94);
  border-bottom: 1px solid rgba(0, 229, 255, 0.18);
  flex-shrink: 0;
  backdrop-filter: blur(8px);
  box-shadow: 0 1px 20px rgba(0, 229, 255, 0.08);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.app-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
}

.title-flag { font-size: 1.1rem; }

.title-text {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  background: linear-gradient(90deg, #00e5ff 0%, #7c4dff 50%, #e040fb 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: drop-shadow(0 0 6px rgba(0, 229, 255, 0.4));
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.badge {
  font-size: 0.7rem;
  padding: 0.18rem 0.55rem;
  border-radius: 3px;
  font-weight: 700;
  letter-spacing: 0.05em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.badge-open {
  background: rgba(0, 230, 120, 0.1);
  color: #00e676;
  border: 1px solid rgba(0, 230, 120, 0.35);
  box-shadow: 0 0 8px rgba(0, 230, 120, 0.2);
  animation: pulse-green 2s ease-in-out infinite;
}

.badge-closed {
  background: rgba(255, 60, 60, 0.08);
  color: #ff5555;
  border: 1px solid rgba(255, 60, 60, 0.25);
}

.badge-date {
  background: rgba(124, 77, 255, 0.1);
  color: #bb86fc;
  border: 1px solid rgba(124, 77, 255, 0.3);
  font-size: 0.68rem;
}

@keyframes pulse-green {
  0%, 100% { box-shadow: 0 0 6px rgba(0, 230, 120, 0.2); }
  50%       { box-shadow: 0 0 14px rgba(0, 230, 120, 0.45); }
}

.last-updated {
  font-size: 0.68rem;
  color: rgba(0, 229, 255, 0.28);
  letter-spacing: 0.05em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.main-content {
  flex: 1;
  padding: 0.9rem 1.2rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
