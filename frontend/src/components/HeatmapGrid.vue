<template>
  <div class="heatmap-container">
    <div v-if="loading" class="state-msg">
      <span class="loading-dot">▋</span> 載入中…
    </div>
    <div v-else-if="error" class="state-msg error">⚠ {{ error }}</div>
    <div v-else-if="allStocks.length === 0" class="state-msg">暫無資料</div>

    <template v-else>
      <!-- 6×6 grid -->
      <div class="stock-grid">
        <StockCell
          v-for="stock in pageStocks"
          :key="stock.stock_id"
          :stock="stock"
          :mode="mode"
        />
        <!-- 末頁補空格維持 6×6 -->
        <div
          v-for="i in emptyCount"
          :key="`empty-${i}`"
          class="cell-empty"
        />
      </div>

      <!-- 換頁列 -->
      <div class="pagination">
        <button class="page-btn" :disabled="page === 0" @click="prevPage">‹ 上一頁</button>

        <div class="page-dots">
          <button
            v-for="p in totalPages"
            :key="p"
            class="dot"
            :class="{ active: p - 1 === page }"
            @click="page = p - 1"
          >{{ p }}</button>
        </div>

        <span class="page-info">
          第 {{ page + 1 }} / {{ totalPages }} 頁
          &nbsp;·&nbsp;
          排名 {{ pageStart + 1 }}–{{ pageEnd }}（共 {{ allStocks.length }} 檔）
        </span>

        <button class="page-btn" :disabled="page >= totalPages - 1" @click="nextPage">下一頁 ›</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import StockCell from './StockCell.vue'

const COLS = 6
const ROWS = 6
const PAGE_SIZE = COLS * ROWS   // 36 張/頁
const MAX_STOCKS = 300

const store = useStockStore()
const { sectors, loading, error, mode } = storeToRefs(store)
const page = ref(0)

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

const totalPages = computed(() => Math.max(1, Math.ceil(allStocks.value.length / PAGE_SIZE)))
const pageStart = computed(() => page.value * PAGE_SIZE)
const pageEnd = computed(() => Math.min(pageStart.value + PAGE_SIZE, allStocks.value.length))

const pageStocks = computed(() => allStocks.value.slice(pageStart.value, pageEnd.value))
const emptyCount = computed(() => PAGE_SIZE - pageStocks.value.length)

watch(allStocks, () => { page.value = 0 })

function prevPage() { if (page.value > 0) page.value-- }
function nextPage() { if (page.value < totalPages.value - 1) page.value++ }
</script>

<style scoped>
.heatmap-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0.35rem;
  min-height: 0;
}

.stock-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  grid-template-rows: repeat(6, 1fr);
  gap: clamp(4px, 0.55vw, 8px);
  min-height: 0;
}

.cell-empty {
  background: rgba(0, 255, 255, 0.02);
  border: 1px dashed rgba(0, 255, 255, 0.08);
  border-radius: 6px;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  flex-shrink: 0;
  padding: 0.2rem 0;
}

.page-btn {
  background: rgba(0, 255, 255, 0.05);
  color: #00e5ff;
  border: 1px solid rgba(0, 255, 255, 0.3);
  border-radius: 4px;
  padding: 0.3rem 0.9rem;
  font-size: 0.78rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: 0.05em;
}

.page-btn:hover:not(:disabled) {
  background: rgba(0, 255, 255, 0.15);
  border-color: #00e5ff;
  box-shadow: 0 0 8px rgba(0, 255, 255, 0.3);
}

.page-btn:disabled {
  opacity: 0.25;
  cursor: default;
}

.page-dots {
  display: flex;
  gap: 4px;
}

.dot {
  width: 26px;
  height: 26px;
  border-radius: 3px;
  background: rgba(0, 255, 255, 0.05);
  border: 1px solid rgba(0, 255, 255, 0.2);
  color: #555;
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.dot:hover {
  background: rgba(0, 255, 255, 0.12);
  color: #00e5ff;
}

.dot.active {
  background: rgba(0, 229, 255, 0.15);
  border-color: #00e5ff;
  color: #00e5ff;
  font-weight: 700;
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.4);
}

.page-info {
  font-size: 0.72rem;
  color: #444;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.03em;
  white-space: nowrap;
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
  .pagination {
    gap: 0.45rem;
  }

  .page-btn {
    padding: 0.2rem 0.6rem;
    font-size: 0.7rem;
  }

  .dot {
    width: 22px;
    height: 22px;
    font-size: 0.66rem;
  }

  .page-info {
    font-size: 0.66rem;
  }

  .state-msg {
    font-size: 0.88rem;
    padding: 2rem;
  }
}
</style>
