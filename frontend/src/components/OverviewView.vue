<template>
  <div class="overview">
    <div v-if="error && !stockPool.length" class="state-msg error">無法取得行情：{{ error }}</div>
    <template v-else>
      <MarketPulse :summary="summary" />

      <div class="overview-main">
        <ShortlistPanel />
        <div class="overview-side">
          <WatchAlertsPanel />
          <BreadthPanel :summary="summary" />
        </div>
      </div>

      <div class="overview-lower">
        <SectorPanel />
        <SetupPanel />
      </div>

      <footer class="overview-foot">
        <ResearchNote />
        <button class="link-btn" @click="ui.openGuide()">如何使用這份資料</button>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useMarketStore } from '../stores/marketStore'
import { useUiStore } from '../stores/uiStore'
import { marketSummary } from '../utils/analysis'
import MarketPulse from './overview/MarketPulse.vue'
import ShortlistPanel from './overview/ShortlistPanel.vue'
import BreadthPanel from './overview/BreadthPanel.vue'
import SectorPanel from './overview/SectorPanel.vue'
import SetupPanel from './overview/SetupPanel.vue'
import WatchAlertsPanel from './overview/WatchAlertsPanel.vue'
import ResearchNote from './ResearchNote.vue'

const REFRESH_MS = 300_000   // the data changes nightly; ETag makes re-checks cheap

const { stockPool, scores, signals, error } = storeToRefs(useStockStore())
const market = useMarketStore()
const ui = useUiStore()

const summary = computed(() => marketSummary(stockPool.value, {
  scores: scores.value,
  signals: signals.value,
}))

function refresh() {
  if (document.hidden) return
  market.loadTrend()
  market.loadBacktest()
}

let timer = null
onMounted(() => {
  refresh()
  timer = setInterval(refresh, REFRESH_MS)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.overview {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 2px;
}

.overview-main {
  display: grid;
  grid-template-columns: minmax(0, 1.75fr) minmax(320px, 1fr);
  gap: 10px;
  align-items: start;
}

.overview-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.overview-lower {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}

.overview-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px 16px;
  padding: 2px 2px 8px;
}

.link-btn {
  border: none;
  background: none;
  color: var(--accent);
  font-size: 0.75rem;
}
.link-btn:hover { text-decoration: underline; }

@media (max-width: 1100px) {
  .overview-main,
  .overview-lower { grid-template-columns: minmax(0, 1fr); }
}
</style>
