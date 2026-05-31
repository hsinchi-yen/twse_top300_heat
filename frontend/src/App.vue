<template>
  <div class="app-shell" :class="{ embedded: isEmbedded }">
    <header class="topbar">
      <div class="topbar-row1">
        <h1 class="app-title">
          <span class="title-flag">🇹🇼</span>
          <span class="title-text">台股熱力圖</span>
        </h1>
        <div class="topbar-right">
          <!-- 資料日期（非今日時顯示） -->
          <span v-if="activeDate && activeDate !== todayStr" class="badge badge-date">
            📅 {{ activeDate }}
          </span>
          <span v-if="!marketOpen" class="badge badge-closed">◼ 已收盤</span>
          <span v-else class="badge badge-open">● 盤中</span>
          <span class="last-updated mono">{{ formattedTime }}</span>
          <ScoreRefreshBtn />
          <TokenSettings />
        </div>
      </div>
      <div class="topbar-controls">
        <ModeToggle
          :mode="mode"
          :grid-size="gridSize"
          :mobile-density="mobileDensity"
          @mode-change="onModeChange"
          @grid-size-change="onGridSizeChange"
          @density-change="onDensityChange"
        />
      </div>
    </header>

    <main class="main-content">
      <HeatmapGrid v-if="mode !== 'etf'" />
      <EtfGrid v-else />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from './stores/stockStore'
import { useStockData } from './composables/useStockData'
import { useEtfData } from './composables/useEtfData'
import { fetchScores } from './composables/useScoreData'
import { useBreakpoint } from './composables/useBreakpoint'
import ModeToggle from './components/ModeToggle.vue'
import HeatmapGrid from './components/HeatmapGrid.vue'
import EtfGrid from './components/EtfGrid.vue'
import TokenSettings from './components/TokenSettings.vue'
import ScoreRefreshBtn from './components/ScoreRefreshBtn.vue'

const isEmbedded = import.meta.env.VITE_EMBEDDED === 'true'

const store = useStockStore()
const {
  mode, gridSize, mobileDensity,
  marketOpen, updatedAt, date: dataDate, etfDate, etfUpdatedAt,
  scoresLoaded, scoresFetching,
} = storeToRefs(store)
const { isMobile } = useBreakpoint()

useStockData()
useEtfData()
onMounted(fetchScores)

function onModeChange(newMode) {
  store.setMode(newMode)
  if (newMode === 'buy_score' && !scoresLoaded.value && !scoresFetching.value) {
    fetchScores()
  }
}

function onGridSizeChange(n) {
  store.setGridSize(n)
}

function onDensityChange(d) {
  store.setMobileDensity(d)
}

const todayStr = new Date().toLocaleDateString('sv-SE')  // "2026-05-16"

const activeDate = computed(() => mode.value === 'etf' ? etfDate.value : dataDate.value)
const activeUpdatedAt = computed(() => mode.value === 'etf' ? etfUpdatedAt.value : updatedAt.value)

const formattedTime = computed(() => {
  if (!activeUpdatedAt.value) return '— : — : —'
  return new Date(activeUpdatedAt.value).toLocaleTimeString('zh-TW', { hour12: false })
})
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  background: transparent;
  color: #c8d8e8;
  font-family: 'Inter', 'Noto Sans TC', sans-serif;
}

.topbar {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.55rem 1.5rem;
  background: rgba(5, 8, 16, 0.94);
  border-bottom: 1px solid rgba(0, 229, 255, 0.18);
  flex-shrink: 0;
  backdrop-filter: blur(8px);
  box-shadow: 0 1px 20px rgba(0, 229, 255, 0.08);
  position: relative;
  z-index: 200;
}

.topbar-row1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-width: 0;
}

.topbar-controls {
  display: flex;
  align-items: center;
  min-width: 0;
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
  min-width: 0;
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

.app-shell.embedded .topbar {
  backdrop-filter: none;
  box-shadow: none;
  padding: 0.55rem 0.9rem;
}

.app-shell.embedded .title-text {
  font-size: 0.96rem;
  filter: none;
}

.app-shell.embedded .topbar-row1 {
  gap: 0.9rem;
}

.app-shell.embedded .topbar-right {
  gap: 0.45rem;
}

.app-shell.embedded .badge {
  font-size: 0.64rem;
  padding: 0.14rem 0.42rem;
}

.app-shell.embedded .main-content {
  padding: 0.65rem 0.75rem;
}

@media (max-width: 1366px), (max-height: 768px) {
  .topbar {
    padding: 0.4rem 0.75rem;
    gap: 0.25rem;
  }

  .topbar-row1 {
    gap: 0.5rem;
  }

  .title-text {
    font-size: 0.94rem;
    letter-spacing: 0.05em;
  }

  .topbar-right {
    gap: 0.4rem;
  }

  .badge {
    font-size: 0.62rem;
    padding: 0.12rem 0.4rem;
  }

  .last-updated {
    font-size: 0.62rem;
  }

  .main-content {
    padding: 0.55rem 0.65rem;
  }
}

/* ── 手機直屏（≤640px）：topbar 標題列 + 控制列 ── */
@media (max-width: 640px) {
  .topbar {
    padding: 0.35rem 0.6rem;
    gap: 0.2rem;
  }

  .topbar-right {
    gap: 0.3rem;
  }

  .title-text {
    font-size: 0.82rem;
    letter-spacing: 0.03em;
  }

  .badge {
    font-size: 0.6rem;
    padding: 0.1rem 0.32rem;
  }

  .last-updated {
    display: none;
  }

  .main-content {
    padding: 0.3rem 0.35rem;
  }
}
</style>
