<template>
  <div class="etf-container">
    <div v-if="etfLoading && etfs.length === 0" class="state-msg">
      <span class="loading-dot">▋</span> 載入 ETF 資料中…
    </div>
    <div v-else-if="etfError" class="state-msg error">⚠ {{ etfError }}</div>
    <div v-else-if="etfs.length === 0" class="state-msg">暫無 ETF 資料</div>

    <template v-else>
      <!-- dynamic ETF grid -->
      <div class="etf-grid" :style="gridStyle" :data-size="gridSize">
        <EtfCell
          v-for="(etf, idx) in pageEtfs"
          :key="etf.etf_id"
          :etf="etf"
          :rank="pageStart + idx + 1"
        />
        <div
          v-for="i in emptyCount"
          :key="`empty-${i}`"
          class="cell-empty"
        />
      </div>

      <!-- 類型篩選列 -->
      <div class="type-filter">
        <button
          class="type-chip"
          :class="{ active: selectedTypes.size === 0 }"
          @click="clearFilter"
        >全部 ({{ sortedEtfs.length }})</button>
        <button
          v-for="t in availableTypes"
          :key="t.name"
          class="type-chip"
          :class="{ active: selectedTypes.has(t.name) }"
          :data-type="t.name"
          @click="toggleType(t.name)"
        >{{ t.name }} ({{ t.count }})</button>
      </div>

      <!-- 換頁列 + 排序切換 -->
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
          排名 {{ pageStart + 1 }}–{{ pageEnd }}（共 {{ filteredEtfs.length }} 檔 / {{ gridSize }}×{{ gridSize }}）
        </span>

        <!-- 排序切換 + 週轉率說明 -->
        <div class="sort-toggle">
          <button
            class="sort-btn"
            :class="{ active: etfSortBy === 'turnover' }"
            @click="setSortBy('turnover')"
          >週轉率</button>
          <button
            class="sort-btn"
            :class="{ active: etfSortBy === 'asset_scale' }"
            @click="setSortBy('asset_scale')"
          >資產規模</button>
        </div>

        <div class="turnover-info">
          <span class="info-trigger">成交量/持股週轉率 ⓘ</span>
          <div class="info-popover">
            <p class="info-row"><span class="info-label">成交量週轉率</span>關心這檔 ETF 好不好買賣、熱不熱門，應參考此指標。</p>
            <p class="info-row"><span class="info-label">持股週轉率</span>若關心基金有沒有把過多成本浪費在頻繁換股上，則必須檢視此指標（可在卡片 hover 中查看）。</p>
          </div>
        </div>

        <button class="page-btn" :disabled="page >= totalPages - 1" @click="nextPage">下一頁 ›</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import EtfCell from './EtfCell.vue'

const store = useStockStore()
const { etfs, etfLoading, etfError, etfSortBy, gridSize } = storeToRefs(store)

const page = ref(0)
const selectedTypes = ref(new Set())

const pageSize = computed(() => gridSize.value * gridSize.value)

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${gridSize.value}, 1fr)`,
  gridTemplateRows:    `repeat(${gridSize.value}, 1fr)`,
}))

const sortedEtfs = computed(() => {
  const rankKey = etfSortBy.value === 'asset_scale' ? 'asset_scale_rank' : 'turnover_rank'
  return [...etfs.value].sort((a, b) => {
    const ra = a[rankKey] ?? 9999
    const rb = b[rankKey] ?? 9999
    if (ra !== rb) return ra - rb
    return (b.volume ?? 0) - (a.volume ?? 0)
  })
})

// Unique types sorted by frequency for filter chips
const availableTypes = computed(() => {
  const counts = {}
  for (const e of sortedEtfs.value) {
    const t = e.etf_type ?? '—'
    counts[t] = (counts[t] ?? 0) + 1
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }))
})

const filteredEtfs = computed(() => {
  if (selectedTypes.value.size === 0) return sortedEtfs.value
  return sortedEtfs.value.filter(e => selectedTypes.value.has(e.etf_type))
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredEtfs.value.length / pageSize.value)))
const pageStart  = computed(() => page.value * pageSize.value)
const pageEnd    = computed(() => Math.min(pageStart.value + pageSize.value, filteredEtfs.value.length))
const pageEtfs   = computed(() => filteredEtfs.value.slice(pageStart.value, pageEnd.value))
const emptyCount = computed(() => pageSize.value - pageEtfs.value.length)

watch(etfs,     () => { page.value = 0 })
watch(etfSortBy,() => { page.value = 0 })
watch(gridSize, () => { page.value = 0 })

function prevPage() { if (page.value > 0) page.value-- }
function nextPage() { if (page.value < totalPages.value - 1) page.value++ }

function setSortBy(val) {
  store.setEtfSortBy(val)
}

function toggleType(type) {
  const s = new Set(selectedTypes.value)
  if (s.has(type)) s.delete(type)
  else s.add(type)
  selectedTypes.value = s
  page.value = 0
}

function clearFilter() {
  selectedTypes.value = new Set()
  page.value = 0
}
</script>

<style scoped>
.etf-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0.3rem;
  min-height: 0;
}

.etf-grid {
  flex: 1;
  display: grid;
  gap: clamp(4px, 0.55vw, 8px);
  min-height: 0;
}

.etf-grid[data-size="4"] { gap: clamp(6px, 0.7vw, 12px); }
.etf-grid[data-size="5"] { gap: clamp(5px, 0.6vw, 10px); }

.cell-empty {
  background: rgba(255, 179, 0, 0.02);
  border: 1px dashed rgba(255, 179, 0, 0.08);
  border-radius: 6px;
}

/* ── 類型篩選列 ── */
.type-filter {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  flex-shrink: 0;
  padding: 0.1rem 0;
}

.type-chip {
  padding: 2px 7px;
  border-radius: 3px;
  border: 1px solid rgba(255, 179, 0, 0.18);
  background: rgba(255, 179, 0, 0.04);
  color: rgba(255, 179, 0, 0.38);
  font-size: 0.62rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: all 0.13s;
  white-space: nowrap;
}
.type-chip:hover {
  color: rgba(255, 179, 0, 0.75);
  border-color: rgba(255, 179, 0, 0.35);
  background: rgba(255, 179, 0, 0.09);
}
.type-chip.active {
  color: #ffb300;
  border-color: #ffb300;
  background: rgba(255, 179, 0, 0.14);
  box-shadow: 0 0 6px rgba(255, 179, 0, 0.22);
}

/* Type-specific active tint for filter chips */
.type-chip.active[data-type="國外股"] { color: #50c8ff; border-color: #50c8ff; background: rgba(80,200,255,0.12); box-shadow: 0 0 6px rgba(80,200,255,0.2); }
.type-chip.active[data-type="多資產"] { color: #b464ff; border-color: #b464ff; background: rgba(180,100,255,0.12); box-shadow: 0 0 6px rgba(180,100,255,0.2); }
.type-chip.active[data-type="槓桿"]  { color: #ff643c; border-color: #ff643c; background: rgba(255,100,60,0.12);  box-shadow: 0 0 6px rgba(255,100,60,0.2); }
.type-chip.active[data-type="反向"]  { color: #ff3cb4; border-color: #ff3cb4; background: rgba(255,60,180,0.12);  box-shadow: 0 0 6px rgba(255,60,180,0.2); }
.type-chip.active[data-type="期貨"]  { color: #ff9632; border-color: #ff9632; background: rgba(255,150,50,0.12);  box-shadow: 0 0 6px rgba(255,150,50,0.2); }
.type-chip.active[data-type="債券"]  { color: #64b4ff; border-color: #64b4ff; background: rgba(100,180,255,0.12); box-shadow: 0 0 6px rgba(100,180,255,0.2); }
.type-chip.active[data-type="貨幣"]  { color: #50e6b4; border-color: #50e6b4; background: rgba(80,230,180,0.12);  box-shadow: 0 0 6px rgba(80,230,180,0.2); }

/* ── 換頁列 ── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.65rem;
  flex-wrap: wrap;
  flex-shrink: 0;
  padding: 0.1rem 0;
}

.page-btn {
  background: rgba(255, 179, 0, 0.05);
  color: #ffb300;
  border: 1px solid rgba(255, 179, 0, 0.3);
  border-radius: 4px;
  padding: 0.3rem 0.9rem;
  font-size: 0.78rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: 0.05em;
}
.page-btn:hover:not(:disabled) {
  background: rgba(255, 179, 0, 0.14);
  border-color: #ffb300;
  box-shadow: 0 0 8px rgba(255, 179, 0, 0.3);
}
.page-btn:disabled { opacity: 0.25; cursor: default; }

.page-dots { display: flex; gap: 4px; flex-wrap: wrap; justify-content: center; }

.dot {
  width: 26px;
  height: 26px;
  border-radius: 3px;
  background: rgba(255, 179, 0, 0.05);
  border: 1px solid rgba(255, 179, 0, 0.2);
  color: #555;
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.dot:hover { background: rgba(255, 179, 0, 0.12); color: #ffb300; }
.dot.active {
  background: rgba(255, 179, 0, 0.15);
  border-color: #ffb300;
  color: #ffb300;
  font-weight: 700;
  box-shadow: 0 0 8px rgba(255, 179, 0, 0.4);
}

.page-info {
  font-size: 0.72rem;
  color: #554400;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

/* ── 排序切換 ── */
.sort-toggle {
  display: flex;
  gap: 3px;
  background: rgba(255, 179, 0, 0.04);
  border: 1px solid rgba(255, 179, 0, 0.15);
  border-radius: 4px;
  padding: 2px;
}

.sort-btn {
  padding: 0.18rem 0.6rem;
  border-radius: 3px;
  border: none;
  background: transparent;
  color: rgba(255, 179, 0, 0.4);
  font-size: 0.68rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.sort-btn:hover { color: #ffb300; background: rgba(255, 179, 0, 0.1); }
.sort-btn.active {
  background: rgba(255, 179, 0, 0.18);
  color: #ffb300;
  box-shadow: 0 0 6px rgba(255, 179, 0, 0.25);
}

/* ── 週轉率說明 ── */
.turnover-info {
  position: relative;
  display: flex;
  align-items: center;
}

.info-trigger {
  font-size: 0.66rem;
  color: rgba(255, 179, 0, 0.45);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.03em;
  cursor: default;
  border-bottom: 1px dashed rgba(255, 179, 0, 0.25);
  white-space: nowrap;
  user-select: none;
  transition: color 0.15s;
}
.turnover-info:hover .info-trigger { color: #ffb300; }

.info-popover {
  display: none;
  position: absolute;
  bottom: calc(100% + 8px);
  right: 0;
  width: 280px;
  background: rgba(12, 9, 2, 0.96);
  border: 1px solid rgba(255, 179, 0, 0.35);
  border-radius: 6px;
  padding: 10px 12px;
  z-index: 100;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.6), 0 0 12px rgba(255, 179, 0, 0.12);
}
.turnover-info:hover .info-popover { display: flex; flex-direction: column; gap: 8px; }

.info-row {
  margin: 0;
  font-size: 0.68rem;
  color: rgba(255, 220, 160, 0.8);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.02em;
  line-height: 1.5;
}

.info-label {
  display: block;
  font-size: 0.62rem;
  font-weight: 700;
  color: #ffb300;
  margin-bottom: 2px;
  letter-spacing: 0.04em;
}

/* ── 狀態訊息 ── */
.state-msg {
  color: #554400;
  font-size: 1rem;
  text-align: center;
  padding: 4rem;
  flex: 1;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.state-msg.error { color: #ff8c42; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
.loading-dot { animation: blink 1s step-start infinite; color: #ffb300; }

@media (max-width: 1366px), (max-height: 768px) {
  .pagination { gap: 0.4rem; }
  .page-btn { padding: 0.2rem 0.6rem; font-size: 0.7rem; }
  .dot { width: 22px; height: 22px; font-size: 0.66rem; }
  .page-info { font-size: 0.66rem; }
  .sort-btn { font-size: 0.62rem; padding: 0.14rem 0.45rem; }
  .info-trigger { font-size: 0.60rem; }
  .info-popover { width: 240px; font-size: 0.62rem; }
  .state-msg { font-size: 0.88rem; padding: 2rem; }
  .type-chip { font-size: 0.56rem; padding: 1px 5px; }
}
</style>
