<template>
  <div class="app-shell" :class="{ embedded: isEmbedded }">
    <header class="topbar">
      <h1 class="brand">
        <svg class="brand-mark" width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
          <rect x="1" y="1" width="9" height="12" rx="2.5" fill="var(--pct-up)" />
          <rect x="12" y="1" width="9" height="7" rx="2.5" fill="var(--accent)" />
          <rect x="1" y="15" width="9" height="6" rx="2.5" fill="var(--accent)" opacity="0.45" />
          <rect x="12" y="10" width="9" height="11" rx="2.5" fill="var(--pct-down)" />
        </svg>
        <span class="brand-text">台股熱力圖</span>
      </h1>

      <AppNav
        :mode="mode"
        :heatmap-mode="heatmapMode"
        :watch-count="watchItems.length"
        @mode-change="onModeChange"
      />

      <GlobalSearch />

      <div class="topbar-right">
        <ScoreProgress v-if="showScoreStatus" />
        <span class="market-status" :class="{ open: marketOpen }">
          <i class="status-dot" />{{ marketOpen ? '盤中' : '已收盤' }}
        </span>
        <span class="data-time num" :title="`資料日期 ${activeDate}`">{{ timeLabel }}</span>
        <ScoreRefreshBtn v-if="showScoreStatus" />
        <button class="icon-btn guide-btn" title="使用說明" aria-label="使用說明" @click="ui.openGuide()">
          <Icon name="help" />
        </button>
        <button class="icon-btn settings-btn" title="設定" aria-label="設定" @click="ui.openSettings()">
          <Icon name="settings" />
        </button>
        <button
          class="icon-btn theme-toggle"
          :aria-label="themeStore.theme === 'dark' ? '切換亮色模式' : '切換暗色模式'"
          :title="themeStore.theme === 'dark' ? '亮色' : '暗色'"
          @click="themeStore.toggle()"
        >
          <Icon :name="themeStore.theme === 'dark' ? 'sun' : 'moon'" />
        </button>
      </div>
    </header>

    <main class="main-content">
      <OverviewView v-if="mode === 'overview'" />
      <EtfGrid v-else-if="mode === 'etf'" />
      <WatchlistView v-else-if="mode === 'watchlist'" />
      <HeatmapGrid v-else @mode-change="onModeChange" />
    </main>

    <StockDrawer />
    <GuideModal />
    <SettingsModal />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from './stores/stockStore'
import { useThemeStore } from './stores/themeStore'
import { useWatchlistStore } from './stores/watchlistStore'
import { useUiStore } from './stores/uiStore'
import { useStockData } from './composables/useStockData'
import { useWatchlistData } from './composables/useWatchlistData'
import { useSignalsData } from './composables/useSignalsData'
import { useEtfData } from './composables/useEtfData'
import { fetchScores, useScorePolling } from './composables/useScoreData'
import { dataTimeLabel } from './utils/format'
import AppNav from './components/AppNav.vue'
import GlobalSearch from './components/GlobalSearch.vue'
import Icon from './components/Icon.vue'
import OverviewView from './components/OverviewView.vue'
import HeatmapGrid from './components/HeatmapGrid.vue'
import EtfGrid from './components/EtfGrid.vue'
import WatchlistView from './components/WatchlistView.vue'
import StockDrawer from './components/StockDrawer.vue'
import GuideModal from './components/GuideModal.vue'
import SettingsModal from './components/SettingsModal.vue'
import ScoreRefreshBtn from './components/ScoreRefreshBtn.vue'
import ScoreProgress from './components/ScoreProgress.vue'

const isEmbedded = import.meta.env.VITE_EMBEDDED === 'true'

const store = useStockStore()
const themeStore = useThemeStore()
const ui = useUiStore()
const {
  mode, heatmapMode, marketOpen, updatedAt, date: dataDate, etfDate, etfUpdatedAt,
  scoresLoaded, scoresFetching,
} = storeToRefs(store)
const { items: watchItems } = storeToRefs(useWatchlistStore())

useStockData()
useEtfData()
useWatchlistData()
useSignalsData()
useScorePolling()

function onModeChange(newMode) {
  store.setMode(newMode)
  const needsScores = newMode === 'buy_score' || newMode === 'watchlist' || newMode === 'overview'
  if (needsScores && !scoresLoaded.value && !scoresFetching.value) {
    fetchScores()
  }
}

const showScoreStatus = computed(() => ['overview', 'buy_score', 'watchlist'].includes(mode.value))

const activeDate = computed(() => (mode.value === 'etf' ? etfDate.value : dataDate.value))
const activeUpdatedAt = computed(() => (mode.value === 'etf' ? etfUpdatedAt.value : updatedAt.value))

const timeLabel = computed(() => dataTimeLabel(activeDate.value, activeUpdatedAt.value))
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  color: var(--text-primary);
}

.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  min-height: 52px;
  padding: 8px 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--border-subtle);
  position: relative;
  z-index: 200;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 4px;
  flex-shrink: 0;
}

.brand-text {
  font-size: 1rem;
  font-weight: 700;
  white-space: nowrap;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  min-width: 0;
}

.market-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  white-space: nowrap;
}
.market-status.open { color: var(--text-primary); font-weight: 500; }

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
}
.market-status.open .status-dot { background: var(--pct-down); }

.data-time {
  font-size: 0.8125rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.main-content {
  flex: 1;
  min-height: 0;
  padding: 10px 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

@media (max-width: 1100px) {
  .brand-text { display: none; }
}

@media (max-width: 900px) {
  .data-time { display: none; }
}

@media (max-width: 768px) {
  .topbar { gap: 6px; padding: 6px 8px; min-height: 46px; }
  .brand { margin-right: 0; }
  .topbar-right { gap: 0; flex-shrink: 0; }
  .market-status { font-size: 0; gap: 0; }
  .main-content {
    padding: 6px 6px calc(64px + env(safe-area-inset-bottom));
  }
}
</style>
