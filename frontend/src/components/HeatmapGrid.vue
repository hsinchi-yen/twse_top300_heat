<template>
  <div class="heatmap-container">
    <div v-if="loading" class="state-msg">
      <span class="loading-dot">▋</span> 載入中…
    </div>
    <div v-else-if="error" class="state-msg error">⚠ {{ error }}</div>
    <div v-else-if="allStocks.length === 0" class="state-msg">
      {{ mode === 'buy_score' && scoresFetching ? '計分中…' : '暫無資料' }}
    </div>

    <template v-else>
      <!-- dynamic grid -->
      <div
        class="stock-grid"
        :style="gridStyle"
        :data-size="gridSize"
        :data-density="isMobile ? mobileDensity : null"
        @pointerdown="onPointerDown"
        @pointerup="onPointerUp"
      >
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
        <!-- 末頁補空格維持格子排列 -->
        <div
          v-for="i in emptyCount"
          :key="`empty-${i}`"
          class="cell-empty"
        />
      </div>

      <!-- 換頁列 -->
      <div class="pagination" :class="{ mobile: isMobile }">
        <button class="page-btn" :disabled="page === 0" @click="prevPage">
          {{ isMobile ? '‹' : '‹ 上一頁' }}
        </button>

        <!-- desktop: 頁碼點 -->
        <div v-if="!isMobile" class="page-dots">
          <button
            v-for="p in totalPages"
            :key="p"
            class="dot"
            :class="{ active: p - 1 === page }"
            @click="page = p - 1"
          >{{ p }}</button>
        </div>

        <!-- mobile: 跳頁下拉 -->
        <select v-else class="page-jump" :value="page" @change="onJump">
          <option v-for="p in totalPages" :key="p" :value="p - 1">
            第 {{ p }} / {{ totalPages }} 頁
          </option>
        </select>

        <span class="page-info">
          <template v-if="!isMobile">
            第 {{ page + 1 }} / {{ totalPages }} 頁
            &nbsp;·&nbsp;
            排名 {{ pageStart + 1 }}–{{ pageEnd }}（共 {{ allStocks.length }} 檔 / {{ cols }}×{{ rows }}）
          </template>
          <template v-else>
            {{ pageStart + 1 }}–{{ pageEnd }} / {{ allStocks.length }}
          </template>
        </span>

        <button class="page-btn" :disabled="page >= totalPages - 1" @click="nextPage">
          {{ isMobile ? '›' : '下一頁 ›' }}
        </button>

        <div class="search-box">
          <input
            v-model="searchQuery"
            type="text"
            inputmode="numeric"
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
import { useBreakpoint } from '../composables/useBreakpoint'
import { MAX_STOCKS, MOBILE_DENSITY } from '../constants'
import StockCell from './StockCell.vue'

const store = useStockStore()
const {
  sectors, loading, error, mode, gridSize, mobileDensity,
  scores, scoresLoaded, scoresFetching,
} = storeToRefs(store)
const { isMobile } = useBreakpoint()

const page = ref(0)
const searchQuery = ref('')
const searchError = ref('')
const highlightedStockId = ref('')
let highlightTimer = null

// ── grid geometry: desktop uses gridSize²; mobile uses 2×N density ──
const cols = computed(() => isMobile.value ? MOBILE_DENSITY[mobileDensity.value].cols : gridSize.value)
const rows = computed(() => isMobile.value ? MOBILE_DENSITY[mobileDensity.value].rows : gridSize.value)
const pageSize = computed(() => cols.value * rows.value)

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${cols.value}, 1fr)`,
  gridTemplateRows:    `repeat(${rows.value}, 1fr)`,
}))

// stock_id → enriched stock (price/change for heat color), built from display pool
const stockLookup = computed(() => {
  const m = {}
  for (const sector of sectors.value) {
    for (const s of sector.stocks ?? []) {
      m[s.stock_id] = { ...s, sector: sector.name }
    }
  }
  return m
})

// 攤平所有 sector，依當前模式排序
// volume: backend volume_rank；turnover: 前端用 turnover_rate 重排；buy_score: 分數高→低
const allStocks = computed(() => {
  if (mode.value === 'buy_score') {
    const flat = []
    for (const sector of sectors.value) {
      for (const s of sector.stocks ?? []) {
        const sc = scores.value[s.stock_id]
        flat.push({ ...s, sector: sector.name,
          score: sc?.score ?? null, max_score: sc?.max_score ?? null })
      }
    }
    flat.sort((a, b) => {
      if (a.score === null && b.score === null) return 0
      if (a.score === null) return 1
      if (b.score === null) return -1
      return b.score - a.score
    })
    return flat.slice(0, MAX_STOCKS).map((s, i) => ({ ...s, rank: i + 1 }))
  }

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
watch(pageSize,  () => { page.value = 0 })
watch(mode,      clearSearch)

function prevPage() { if (page.value > 0) page.value-- }
function nextPage() { if (page.value < totalPages.value - 1) page.value++ }
function onJump(e)  { page.value = Number(e.target.value) }

// ── swipe to change page (mobile only) ──
let touchStartX = null
function onPointerDown(e) {
  if (!isMobile.value || e.pointerType === 'mouse') { touchStartX = null; return }
  touchStartX = e.clientX
}
function onPointerUp(e) {
  if (touchStartX === null) return
  const dx = e.clientX - touchStartX
  touchStartX = null
  if (Math.abs(dx) < 50) return
  if (dx < 0) nextPage()
  else prevPage()
}

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
  /* columns/rows set via :style binding */
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

/* mobile 跳頁下拉 */
.page-jump {
  background: #0a1520;
  color: #00e5ff;
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 4px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  padding: 0.4rem 0.6rem;
  min-height: 44px;
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

/* ── 手機直屏：字體放大（覆蓋 StockCell 的 scoped 字體大小）── */

/* 2x2 / 2x3：200% 方便老花眼閱讀 */
@media (max-width: 768px) {
  .stock-grid:not([data-density="3x3"]) :deep(.cell-rank)   { font-size: 1.16rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-sector) { font-size: 1.0rem;  }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-code)   { font-size: 1.24rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-price)  { font-size: 1.36rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-name)   { font-size: 1.9rem;  }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-score)  { font-size: 1.16rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-value)  { font-size: 1.24rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-pct)    { font-size: 1.56rem; }
}

/* 3x3：150%（密度較高，適度放大即可） */
@media (max-width: 768px) {
  .stock-grid[data-density="3x3"] :deep(.cell-rank)   { font-size: 0.87rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-sector) { font-size: 0.75rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-code)   { font-size: 0.93rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-price)  { font-size: 1.02rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-name)   { font-size: 1.43rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-score)  { font-size: 0.87rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-value)  { font-size: 0.93rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-pct)    { font-size: 1.17rem; }
}

/* ── 真手機斷點：觸控導向佈局 ── */
@media (max-width: 768px) {
  .heatmap-container { gap: 0.5rem; }

  .pagination.mobile {
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 0.3rem 0;
  }

  .pagination.mobile .page-btn {
    min-width: 44px;
    min-height: 44px;
    font-size: 1.1rem;
    padding: 0.3rem 0.7rem;
  }

  .pagination.mobile .page-info {
    font-size: 0.72rem;
    order: 4;
    flex-basis: 100%;
    text-align: center;
  }

  .pagination.mobile .search-box {
    order: 5;
    flex-basis: 100%;
    margin-left: 0;
    justify-content: center;
  }

  .pagination.mobile .search-input {
    width: 100%;
    max-width: 240px;
    font-size: 0.85rem;
    min-height: 40px;
    padding: 0.4rem 1.8rem 0.4rem 0.7rem;
  }
}
</style>
