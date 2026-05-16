<template>
  <div class="heatmap-container">
    <div v-if="loading" class="state-msg">
      <span class="loading-dot">▋</span> 載入中…
    </div>
    <div v-else-if="error" class="state-msg error">! {{ error }}</div>
    <div v-else-if="allStocks.length === 0" class="state-msg">暫無資料</div>

    <template v-else>
      <div class="grid-summary mono">
        顯示 TOP {{ allStocks.length }}（按題材分區）
      </div>

      <div class="sector-grid">
        <SectorBlock
          v-for="sector in groupedSectors"
          :key="sector.name"
          :sector="sector"
          :mode="mode"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import SectorBlock from './SectorBlock.vue'

const MAX_STOCKS = 100

const store = useStockStore()
const { sectors, loading, error, mode } = storeToRefs(store)

// 攤平所有 sector，加上 sector 標籤，依 rank 排序
const allStocks = computed(() => {
  const flat = []
  for (const sector of sectors.value) {
    for (const stock of sector.stocks ?? []) {
      flat.push({ ...stock, sector: sector.name })
    }
  }
  return flat
    .sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999))
    .slice(0, MAX_STOCKS)
})

const groupedSectors = computed(() => {
  const groups = new Map()
  for (const stock of allStocks.value) {
    const key = stock.sector || '其他'
    if (!groups.has(key)) {
      groups.set(key, { name: key, stocks: [] })
    }
    groups.get(key).stocks.push(stock)
  }
  return Array.from(groups.values())
})
</script>

<style scoped>
.heatmap-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0.4rem;
  min-height: 0;
}

.grid-summary {
  color: rgba(0, 229, 255, 0.45);
  font-size: 0.72rem;
  letter-spacing: 0.04em;
}

.sector-grid {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.5rem;
  align-content: start;
  padding-right: 2px;
}

/* ── 狀態訊息 ── */
.state-msg {
  color: #444;
  font-size: 1rem;
  text-align: center;
  padding: 4rem;
  flex: 1;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.state-msg.error { color: #ff4444; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
.loading-dot {
  animation: blink 1s step-start infinite;
  color: #00e5ff;
}

@media (max-width: 1366px), (max-height: 768px) {
  .grid-summary {
    font-size: 0.66rem;
  }

  .sector-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.4rem;
  }

  .state-msg {
    font-size: 0.88rem;
    padding: 2rem;
  }
}
</style>
