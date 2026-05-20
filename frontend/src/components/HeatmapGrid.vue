<template>
  <div class="heatmap-container">
    <div v-if="loading" class="state-msg">
      <span class="loading-dot">▋</span> 載入中…
    </div>
    <div v-else-if="error" class="state-msg error">⚠ {{ error }}</div>
    <div v-else-if="allStocks.length === 0" class="state-msg">暫無資料</div>

    <template v-else>
      <!-- dynamic grid -->
      <div class="stock-grid" :style="gridStyle" :data-size="gridSize">
        <StockCell
          v-for="stock in pageStocks"
          :key="stock.stock_id"
          :stock="stock"
          :mode="mode"
          :highlighted="stock.stock_id === highlightedStockId"
          :buy-score="scores[stock.stock_id] ?? null"
          :scores-loaded="scoresLoaded"
          :scores-fetching="scoresFetching"
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
          排名 {{ pageStart + 1 }}–{{ pageEnd }}（共 {{ allStocks.length }} 檔 / {{ gridSize }}×{{ gridSize }}）
        </span>

        <button class="page-btn" :disabled="page >= totalPages - 1" @click="nextPage">下一頁 ›</button>

        <div class="search-box">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="輸入股號 Enter"
            maxlength="6"
            @keydown.enter="doSearch"
            class="search-input"
          />
          <button v-if="searchQuery" class="search-clear" @click="clearSearch">×</button>
          <p v-if="searchError" class="search-error">{{ searchError }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import StockCell from './StockCell.vue'

const MAX_STOCKS = 360

const store = useStockStore()
const { sectors, loading, error, mode, gridSize, scores, scoresLoaded, scoresFetching } = storeToRefs(store)
const page = ref(0)
const searchQuery = ref('')
const searchError = ref('')
const highlightedStockId = ref('')
let highlightTimer = null

const pageSize = computed(() => gridSize.value * gridSize.value)

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${gridSize.value}, 1fr)`,
  gridTemplateRows:    `repeat(${gridSize.value}, 1fr)`,
}))

// 攤平所有 sector，加上 sector 標籤，依當前模式排序
// backend 固定回 volume_rank 作為 rank 欄位；週轉率模式在前端用 turnover_rate 重排
const allStocks = computed(() => {
  const flat = []
  for (const sector of sectors.value) {
    for (const stock of sector.stocks ?? []) {
      flat.push({ ...stock, sector: sector.name })
    }
  }
  const sorted = mode.value === 'turnover'
    ? flat.slice().sort((a, b) => (b.turnover_rate ?? 0) - (a.turnover_rate ?? 0))
    : flat.slice().sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999))
  return sorted.slice(0, MAX_STOCKS)
})

const totalPages = computed(() => Math.max(1, Math.ceil(allStocks.value.length / pageSize.value)))
const pageStart = computed(() => page.value * pageSize.value)
const pageEnd = computed(() => Math.min(pageStart.value + pageSize.value, allStocks.value.length))

const pageStocks = computed(() => allStocks.value.slice(pageStart.value, pageEnd.value))
const emptyCount = computed(() => pageSize.value - pageStocks.value.length)

watch(allStocks, () => { page.value = 0 })
watch(gridSize,  () => { page.value = 0 })
watch(mode,      clearSearch)

function prevPage() { if (page.value > 0) page.value-- }
function nextPage() { if (page.value < totalPages.value - 1) page.value++ }

function doSearch() {
  const query = searchQuery.value.trim()
  searchError.value = ''
  highlightedStockId.value = ''
  if (highlightTimer) { clearTimeout(highlightTimer); highlightTimer = null }
  if (!query) return

  const idx = allStocks.value.findIndex(s => s.stock_id === query)
  if (idx === -1) {
    searchError.value = `找不到 ${query}，不在 Top ${allStocks.value.length} 範圍內`
    return
  }
  page.value = Math.floor(idx / pageSize.value)
  highlightedStockId.value = query
  highlightTimer = setTimeout(() => { highlightedStockId.value = '' }, 3000)
}

function clearSearch() {
  searchQuery.value = ''
  searchError.value = ''
  highlightedStockId.value = ''
  if (highlightTimer) { clearTimeout(highlightTimer); highlightTimer = null }
}
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
  /* columns/rows set via :style binding from gridSize */
  gap: clamp(4px, 0.55vw, 8px);
  min-height: 0;
}

/* 4×4：卡片大，gap 稍寬；字體在 StockCell 用 clamp 自動放大 */
.stock-grid[data-size="4"] { gap: clamp(6px, 0.7vw, 12px); }
.stock-grid[data-size="5"] { gap: clamp(5px, 0.6vw, 10px); }

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

/* ── 搜尋框 ── */
.search-box {
  position: relative;
  display: inline-flex;
  align-items: center;
  margin-left: auto;
}

.search-input {
  background: #0a1520;
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 4px;
  color: #a0d2f0;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.78rem;
  padding: 0.28rem 1.8rem 0.28rem 0.6rem;
  width: 130px;
  letter-spacing: 0.05em;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.search-input::placeholder {
  color: rgba(0, 229, 255, 0.25);
  font-size: 0.7rem;
}

.search-input:focus {
  border-color: #00e5ff;
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.3);
}

.search-clear {
  position: absolute;
  right: 5px;
  background: none;
  border: none;
  color: rgba(0, 229, 255, 0.4);
  font-size: 1rem;
  cursor: pointer;
  padding: 0 3px;
  line-height: 1;
  transition: color 0.15s;
}

.search-clear:hover { color: #00e5ff; }

.search-error {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 3px;
  font-size: 0.65rem;
  color: #ff4444;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  white-space: nowrap;
  pointer-events: none;
  z-index: 10;
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

  .search-input {
    font-size: 0.7rem;
    width: 110px;
    padding: 0.22rem 1.6rem 0.22rem 0.5rem;
  }

  .state-msg {
    font-size: 0.88rem;
    padding: 2rem;
  }
}
</style>
