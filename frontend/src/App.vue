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
          <button
            class="theme-toggle"
            @click="themeStore.toggle()"
            :aria-label="themeStore.theme === 'dark' ? '切換亮色模式' : '切換暗色模式'"
            :title="themeStore.theme === 'dark' ? '亮色' : '暗色'"
          >
            <span v-if="themeStore.theme === 'dark'">☀</span>
            <span v-else>🌙</span>
          </button>
        </div>
      </div>
      <div class="topbar-controls">
        <ModeToggle
          :mode="mode"
          :grid-size="gridSize"
          :mobile-density="mobileDensity"
          :tablet-density="tabletDensity"
          @mode-change="onModeChange"
          @grid-size-change="onGridSizeChange"
          @density-change="onDensityChange"
          @tablet-density-change="onTabletDensityChange"
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
import { useThemeStore } from './stores/themeStore'
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
const themeStore = useThemeStore()
const {
  mode, gridSize, mobileDensity, tabletDensity,
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

function onTabletDensityChange(d) {
  store.setTabletDensity(d)
}

const todayStr = new Date().toLocaleDateString('sv-SE')

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
  color: var(--text-primary);
  font-family: 'Inter', 'Noto Sans TC', sans-serif;
}

.topbar {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.55rem 1.5rem;
  background: var(--topbar-bg);
  border-bottom: 1px solid var(--topbar-border);
  flex-shrink: 0;
  backdrop-filter: blur(var(--topbar-blur, 8px));
  -webkit-backdrop-filter: blur(var(--topbar-blur, 8px));
  box-shadow: 0 1px 20px var(--topbar-shadow);
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
  background: linear-gradient(90deg, var(--title-from) 0%, var(--title-mid) 50%, var(--title-to) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: drop-shadow(0 0 6px var(--title-shadow));
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
  background: var(--badge-open-bg);
  color: var(--badge-open-color);
  border: 1px solid var(--badge-open-border);
  animation: pulse-green 2s ease-in-out infinite;
}

.badge-closed {
  background: var(--badge-closed-bg);
  color: var(--badge-closed-color);
  border: 1px solid var(--badge-closed-border);
}

.badge-date {
  background: var(--badge-date-bg);
  color: var(--badge-date-color);
  border: 1px solid var(--badge-date-border);
  font-size: 0.68rem;
}

@keyframes pulse-green {
  0%, 100% { box-shadow: 0 0 6px var(--badge-open-border); }
  50%       { box-shadow: 0 0 14px var(--badge-open-color); }
}

.last-updated {
  font-size: 0.68rem;
  color: var(--last-updated-color);
  letter-spacing: 0.05em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

/* ── Theme toggle button ── */
.theme-toggle {
  background: var(--border-subtle);
  border: 1px solid var(--border-default);
  color: var(--text-primary);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s, border-color 0.15s;
  padding: 0;
  line-height: 1;
}

.theme-toggle:hover {
  background: var(--border-default);
  border-color: var(--border-strong);
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

  .theme-toggle {
    width: 24px;
    height: 24px;
    font-size: 0.75rem;
  }
}
</style>
