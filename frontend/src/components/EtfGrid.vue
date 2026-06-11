<template>
  <div class="etf-container">
    <div v-if="etfLoading && etfs.length === 0" class="state-msg">
      <span class="loading-dot">▋</span> 載入 ETF 資料中…
    </div>
    <div v-else-if="etfError" class="state-msg error">⚠ {{ etfError }}</div>
    <div v-else-if="etfs.length === 0" class="state-msg">暫無 ETF 資料</div>

    <template v-else>
      <!-- dynamic ETF grid -->
      <div
        class="etf-grid"
        :style="gridStyle"
        :data-size="gridSize"
        :data-density="isMobile ? mobileDensity : (isTablet ? tabletDensity : null)"
        @pointerdown="onPointerDown"
        @pointerup="onPointerUp"
      >
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
      <div class="pagination" :class="{ mobile: isMobile }">
        <button class="page-btn" :disabled="page === 0" @click="prevPage">
          {{ isMobile ? '‹' : '‹ 上一頁' }}
        </button>

        <!-- desktop/tablet: 頁碼點 -->
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
            排名 {{ pageStart + 1 }}–{{ pageEnd }}（共 {{ filteredEtfs.length }} 檔 / {{ cols }}×{{ rows }}）
          </template>
          <template v-else>
            {{ pageStart + 1 }}–{{ pageEnd }} / {{ filteredEtfs.length }}
          </template>
        </span>

        <!-- 排序切換 + 週轉率說明（手機隱藏說明） -->
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

        <div v-if="!isMobile" class="turnover-info">
          <span class="info-trigger">成交量/持股週轉率 ⓘ</span>
          <div class="info-popover">
            <p class="info-row"><span class="info-label">成交量週轉率</span>關心這檔 ETF 好不好買賣、熱不熱門，應參考此指標。</p>
            <p class="info-row"><span class="info-label">持股週轉率</span>若關心基金有沒有把過多成本浪費在頻繁換股上，則必須檢視此指標（可在卡片 hover 中查看）。</p>
          </div>
        </div>

        <button class="page-btn" :disabled="page >= totalPages - 1" @click="nextPage">
          {{ isMobile ? '›' : '下一頁 ›' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useBreakpoint } from '../composables/useBreakpoint'
import { MOBILE_DENSITY, TABLET_DENSITY } from '../constants'
import EtfCell from './EtfCell.vue'

const store = useStockStore()
const { etfs, etfLoading, etfError, etfSortBy, gridSize, mobileDensity, tabletDensity } = storeToRefs(store)
const { isMobile, isTablet } = useBreakpoint()

const page = ref(0)
const selectedTypes = ref(new Set())

// ── grid geometry ──
const cols = computed(() => {
  if (isMobile.value)  return MOBILE_DENSITY[mobileDensity.value].cols
  if (isTablet.value)  return TABLET_DENSITY[tabletDensity.value].cols
  return gridSize.value
})
const rows = computed(() => {
  if (isMobile.value)  return MOBILE_DENSITY[mobileDensity.value].rows
  if (isTablet.value)  return TABLET_DENSITY[tabletDensity.value].rows
  return gridSize.value
})
const pageSize = computed(() => cols.value * rows.value)

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${cols.value}, 1fr)`,
  gridTemplateRows:    `repeat(${rows.value}, 1fr)`,
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

watch(etfs,      () => { page.value = 0 })
watch(etfSortBy, () => { page.value = 0 })
watch(pageSize,  () => { page.value = 0 })

function prevPage() { if (page.value > 0) page.value-- }
function nextPage() { if (page.value < totalPages.value - 1) page.value++ }
function onJump(e)  { page.value = Number(e.target.value) }

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

function setSortBy(val) { store.setEtfSortBy(val) }

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
  background: var(--etf-cell-empty-bg);
  border: 1px dashed var(--etf-cell-empty-border);
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
  border: 1px solid color-mix(in srgb, var(--accent-etf) 18%, transparent);
  background: color-mix(in srgb, var(--accent-etf) 4%, transparent);
  color: color-mix(in srgb, var(--accent-etf) 38%, transparent);
  font-size: 0.62rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: all 0.13s;
  white-space: nowrap;
}
.type-chip:hover {
  color: color-mix(in srgb, var(--accent-etf) 75%, transparent);
  border-color: color-mix(in srgb, var(--accent-etf) 35%, transparent);
  background: color-mix(in srgb, var(--accent-etf) 9%, transparent);
}
.type-chip.active {
  color: var(--accent-etf);
  border-color: var(--accent-etf);
  background: color-mix(in srgb, var(--accent-etf) 14%, transparent);
  box-shadow: 0 0 6px color-mix(in srgb, var(--accent-etf) 22%, transparent);
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
  background: var(--etf-ctrl-page-btn-bg);
  color: var(--etf-ctrl-page-btn-color);
  border: 1px solid var(--etf-ctrl-page-btn-border);
  border-radius: 4px;
  padding: 0.3rem 0.9rem;
  font-size: 0.78rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: 0.05em;
}
.page-btn:hover:not(:disabled) {
  background: var(--etf-ctrl-page-btn-hover-bg);
  border-color: var(--etf-ctrl-page-btn-color);
  box-shadow: 0 0 8px var(--etf-ctrl-page-btn-hover-shadow);
}
.page-btn:disabled { opacity: 0.25; cursor: default; }

.page-dots { display: flex; gap: 4px; flex-wrap: wrap; justify-content: center; }

.dot {
  width: 26px;
  height: 26px;
  border-radius: 3px;
  background: var(--etf-ctrl-dot-bg);
  border: 1px solid var(--etf-ctrl-dot-border);
  color: var(--ctrl-dot-color);
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.dot:hover { background: var(--etf-ctrl-dot-hover-bg); color: var(--etf-ctrl-dot-hover-color); }
.dot.active {
  background: var(--etf-ctrl-dot-active-bg);
  border-color: var(--etf-ctrl-dot-active-border);
  color: var(--etf-ctrl-dot-active-color);
  font-weight: 700;
  box-shadow: 0 0 8px var(--etf-ctrl-dot-active-shadow);
}

.page-jump {
  background: var(--etf-ctrl-jump-bg);
  color: var(--etf-ctrl-jump-color);
  border: 1px solid var(--etf-ctrl-jump-border);
  border-radius: 4px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  padding: 0.4rem 0.6rem;
  min-height: 44px;
}

.page-info {
  font-size: 0.72rem;
  color: var(--etf-ctrl-page-info-color);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

/* ── 排序切換 ── */
.sort-toggle {
  display: flex;
  gap: 3px;
  background: var(--etf-sort-toggle-bg);
  border: 1px solid var(--etf-sort-toggle-border);
  border-radius: 4px;
  padding: 2px;
}

.sort-btn {
  padding: 0.18rem 0.6rem;
  border-radius: 3px;
  border: none;
  background: transparent;
  color: var(--etf-sort-btn-color);
  font-size: 0.68rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.sort-btn:hover { color: var(--accent-etf); background: var(--etf-sort-btn-hover-bg); }
.sort-btn.active {
  background: var(--etf-sort-btn-active-bg);
  color: var(--accent-etf);
  box-shadow: 0 0 6px var(--etf-sort-btn-active-shadow);
}

/* ── 週轉率說明 ── */
.turnover-info {
  position: relative;
  display: flex;
  align-items: center;
}

.info-trigger {
  font-size: 0.66rem;
  color: var(--etf-info-trigger-color);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.03em;
  cursor: default;
  border-bottom: 1px dashed var(--etf-info-trigger-border);
  white-space: nowrap;
  user-select: none;
  transition: color 0.15s;
}
.turnover-info:hover .info-trigger { color: var(--accent-etf); }

.info-popover {
  display: none;
  position: absolute;
  bottom: calc(100% + 8px);
  right: 0;
  width: 280px;
  background: var(--etf-tooltip-bg);
  border: 1px solid var(--etf-tooltip-border);
  border-radius: 6px;
  padding: 10px 12px;
  z-index: 100;
  box-shadow: 0 4px 24px rgba(0,0,0,0.4), 0 0 12px var(--etf-tooltip-shadow);
}
.turnover-info:hover .info-popover { display: flex; flex-direction: column; gap: 8px; }

.info-row {
  margin: 0;
  font-size: 0.68rem;
  color: var(--etf-tooltip-val);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.02em;
  line-height: 1.5;
}

.info-label {
  display: block;
  font-size: 0.62rem;
  font-weight: 700;
  color: var(--etf-tooltip-label);
  margin-bottom: 2px;
  letter-spacing: 0.04em;
}

/* ── 狀態訊息 ── */
.state-msg {
  color: var(--etf-ctrl-state-color);
  font-size: 1rem;
  text-align: center;
  padding: 4rem;
  flex: 1;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.state-msg.error { color: var(--etf-ctrl-error-color); }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
.loading-dot { animation: blink 1s step-start infinite; color: var(--etf-ctrl-loading-dot); }

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

/* ── 平板（769–1024px）：中等字體 ── */
@media (min-width: 769px) and (max-width: 1024px) {
  .etf-grid :deep(.cell-name)      { font-size: clamp(0.85rem, 1.4vw, 1.1rem); }
  .etf-grid :deep(.cell-type-badge){ font-size: clamp(0.48rem, 0.7vw, 0.6rem); }
  .etf-grid :deep(.cell-scale)     { font-size: clamp(0.55rem, 0.8vw, 0.68rem); }
}

/* ── 真手機斷點：觸控導向佈局 ── */
@media (max-width: 768px) {
  .etf-container { gap: 0.4rem; }

  .type-filter {
    flex-wrap: nowrap;
    overflow-x: auto;
    scrollbar-width: none;
    padding: 0.15rem 0;
    gap: 5px;
  }
  .type-filter::-webkit-scrollbar { display: none; }
  .type-chip {
    flex-shrink: 0;
    font-size: 0.65rem;
    padding: 3px 8px;
    min-height: 32px;
  }

  .pagination.mobile {
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 0.3rem 0;
    justify-content: center;
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

  .pagination.mobile .sort-toggle { order: 3; }

  .pagination.mobile .sort-btn {
    font-size: 0.68rem;
    padding: 0.2rem 0.6rem;
    min-height: 36px;
  }
}
</style>
