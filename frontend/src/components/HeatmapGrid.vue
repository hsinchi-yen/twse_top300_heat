<template>
  <div class="heatmap-container">
    <FilterBar :matched="filteredCount" :total="poolCount">
      <template #lead>
        <div class="segmented sort-control" role="group" aria-label="排序">
          <button
            v-for="s in SORTS"
            :id="`sort-${s.key}`"
            :key="s.key"
            class="segmented__item"
            :class="{ active: mode === s.key }"
            :aria-pressed="mode === s.key"
            @click="emit('mode-change', s.key)"
          >{{ s.label }}</button>
        </div>
      </template>
      <template #trail>
        <DensityControl />
      </template>
    </FilterBar>

    <div v-if="loading && pool.length === 0" class="state-msg">載入中…</div>
    <div v-else-if="error && pool.length === 0" class="state-msg error">無法取得行情：{{ error }}</div>
    <div v-else-if="allStocks.length === 0" class="state-msg">
      {{ (filters.active.length || filters.sector) && poolCount
        ? '目前沒有股票符合篩選條件'
        : mode === 'buy_score' && scoresFetching ? '計分中…' : '暫無資料' }}
    </div>

    <template v-else>
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
          :buy-score="scores[stock.stock_id] ?? null"
          :scores-loaded="scoresLoaded"
          :scores-fetching="scoresFetching"
          :daily="signals[stock.stock_id] ?? null"
          :market-open="marketOpen"
          pinnable
          clickable
          :pinned="wl.isPinned(stock.stock_id)"
          @toggle-pin="wl.toggle"
          @open="ui.openStock"
        />
        <!-- 末頁補空格維持格子排列 -->
        <div v-for="i in emptyCount" :key="`empty-${i}`" />
      </div>

      <Pager
        :page="page"
        :total="totalPages"
        :start="pageStart"
        :end="pageEnd"
        :count="allStocks.length"
        @update:page="page = $event"
      >
        <button v-if="wl.error" class="pin-error" title="點擊關閉" @click="wl.clearError()">{{ wl.error }}</button>
      </Pager>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useWatchlistStore } from '../stores/watchlistStore'
import { useFilterStore } from '../stores/filterStore'
import { useUiStore } from '../stores/uiStore'
import { useBreakpoint } from '../composables/useBreakpoint'
import { MAX_STOCKS, MOBILE_DENSITY } from '../constants'
import { applyFilters, sortByPotential } from '../utils/stockFilters'
import StockCell from './StockCell.vue'
import FilterBar from './FilterBar.vue'
import DensityControl from './DensityControl.vue'
import Pager from './Pager.vue'

const SORTS = [
  { key: 'turnover', label: '週轉率' },
  { key: 'volume', label: '成交量' },
  { key: 'buy_score', label: '買進評分' },
]

const emit = defineEmits(['mode-change'])

const store = useStockStore()
const {
  stockPool: pool, loading, error, mode, gridSize, mobileDensity,
  scores, scoresLoaded, scoresFetching, signals, marketOpen,
} = storeToRefs(store)
const wl = useWatchlistStore()
const filters = useFilterStore()
const ui = useUiStore()
const { isMobile } = useBreakpoint()

const page = ref(0)

// ── grid geometry ──
const cols = computed(() => {
  if (isMobile.value) return MOBILE_DENSITY[mobileDensity.value].cols
  return gridSize.value
})
const rows = computed(() => {
  if (isMobile.value) return MOBILE_DENSITY[mobileDensity.value].rows
  return gridSize.value
})
const pageSize = computed(() => cols.value * rows.value)

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${cols.value}, minmax(0, 1fr))`,
  gridTemplateRows:    `repeat(${rows.value}, minmax(0, 1fr))`,
}))

// 同一批 600 檔（股票 API query 永遠不變），各模式只在前端重排 / 篩選
const poolCount = computed(() => Math.min(pool.value.length, MAX_STOCKS))

function sortForMode(flat) {
  if (mode.value === 'buy_score') {
    const withScore = flat.map((s) => {
      const sc = scores.value[s.stock_id]
      return { ...s, score: sc?.score ?? null, max_score: sc?.max_score ?? null }
    })
    return withScore.sort((a, b) => {
      if (a.score === null && b.score === null) return 0
      if (a.score === null) return 1
      if (b.score === null) return -1
      return b.score - a.score
    })
  }
  return mode.value === 'turnover'
    ? flat.slice().sort((a, b) => (b.turnover_rate ?? 0) - (a.turnover_rate ?? 0))
    : flat.slice().sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999))
}

const allStocks = computed(() => {
  const scope = filters.sector ? pool.value.filter(s => s.sector === filters.sector) : pool.value
  let list
  if (filters.active.length) {
    // 篩選中：先篩，再依潛力排序（pass_rate → 法人近5日）
    const data = { scores: scores.value, signals: signals.value, marketOpen: marketOpen.value }
    list = sortByPotential(applyFilters(scope, filters.active, data), data)
  } else {
    list = sortForMode(scope)
  }
  list = list.slice(0, MAX_STOCKS)
  // 評分模式的 # 是名次；成交量 / 週轉率保留原本的成交量排名
  return mode.value === 'buy_score' ? list.map((s, i) => ({ ...s, rank: i + 1 })) : list
})
const filteredCount = computed(() => allStocks.value.length)

const totalPages = computed(() => Math.max(1, Math.ceil(allStocks.value.length / pageSize.value)))
const pageStart = computed(() => page.value * pageSize.value)
const pageEnd = computed(() => Math.min(pageStart.value + pageSize.value, allStocks.value.length))

const pageStocks = computed(() => allStocks.value.slice(pageStart.value, pageEnd.value))
const emptyCount = computed(() => pageSize.value - pageStocks.value.length)

// Keep the page across polls (which replace the pool with fresh quotes); only a
// change in what is being listed sends the reader back to the first page.
watch([mode, () => filters.active, () => filters.sector], () => { page.value = 0 })
watch(pageSize, () => { page.value = 0 })
watch(totalPages, (n) => { if (page.value > n - 1) page.value = n - 1 })

function prevPage() { if (page.value > 0) page.value-- }
function nextPage() { if (page.value < totalPages.value - 1) page.value++ }

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
</script>

<style scoped>
.heatmap-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 8px;
  min-height: 0;
}

.stock-grid {
  flex: 1;
  display: grid;
  gap: 6px;
  min-height: 0;
}

.pin-error {
  background: none;
  border: none;
  color: var(--pct-up);
  font-size: 0.8125rem;
  white-space: nowrap;
}

/* ── 平板（769–1024px）：中等字體，介於手機與桌機之間（下限 0.7rem） ── */
@media (min-width: 769px) and (max-width: 1024px) {
  .stock-grid :deep(.cell-name)     { font-size: clamp(0.9rem, 1.4vw, 1.1rem); }
  .stock-grid :deep(.cell-code)     { font-size: clamp(0.7rem, 0.85vw, 0.78rem); }
  .stock-grid :deep(.cell-price)    { font-size: clamp(0.75rem, 1.0vw, 0.9rem); }
  .stock-grid :deep(.cell-pct)      { font-size: clamp(0.8rem, 1.2vw, 1.0rem); }
  .stock-grid :deep(.cell-passrate) { font-size: clamp(1rem, 1.6vw, 1.2rem); }
}

/* ── 手機：2x2 / 2x3 放大方便閱讀 ── */
@media (max-width: 768px) {
  .stock-grid:not([data-density="3x3"]) :deep(.cell-rank)   { font-size: 0.875rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-sector) { font-size: 0.875rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-code)   { font-size: 0.9375rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-price)  { font-size: 1.125rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-name)   { font-size: 1.3rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-score)  { font-size: 0.9375rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-value),
  .stock-grid:not([data-density="3x3"]) :deep(.cell-turnover) { font-size: 1rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-pct)    { font-size: 1.3rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-passrate) { font-size: 1.5rem; }
  .stock-grid:not([data-density="3x3"]) :deep(.cell-signal),
  .stock-grid:not([data-density="3x3"]) :deep(.chip)        { font-size: 0.875rem; }

  .stock-grid[data-density="3x3"] :deep(.cell-name)   { font-size: 1rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-pct)    { font-size: 1rem; }
  .stock-grid[data-density="3x3"] :deep(.cell-passrate) { font-size: 1.1rem; }

  /* 名稱完整顯示：手機改為最多兩行換行 */
  .stock-grid :deep(.cell-name) {
    flex-wrap: wrap;
    align-content: center;
    line-height: 1.12;
  }
  .stock-grid :deep(.cell-name-text) {
    white-space: normal;
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}
</style>
