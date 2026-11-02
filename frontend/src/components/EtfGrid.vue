<template>
  <div class="etf-container">
    <div class="etf-toolbar">
      <div class="segmented" role="group" aria-label="ETF 排序">
        <button
          class="segmented__item sort-btn"
          :class="{ active: etfSortBy === 'turnover' }"
          :aria-pressed="etfSortBy === 'turnover'"
          @click="store.setEtfSortBy('turnover')"
        >週轉率</button>
        <button
          class="segmented__item sort-btn"
          :class="{ active: etfSortBy === 'asset_scale' }"
          :aria-pressed="etfSortBy === 'asset_scale'"
          @click="store.setEtfSortBy('asset_scale')"
        >資產規模</button>
      </div>

      <button
        class="chip-btn type-chip"
        :class="{ active: selectedTypes.size === 0 }"
        @click="clearFilter"
      >全部 <span class="num">{{ sortedEtfs.length }}</span></button>
      <button
        v-for="t in availableTypes"
        :key="t.name"
        class="chip-btn type-chip"
        :class="{ active: selectedTypes.has(t.name) }"
        :data-type="t.name"
        @click="toggleType(t.name)"
      >{{ t.name }} <span class="num">{{ t.count }}</span></button>

      <span class="toolbar-spacer" />
      <DensityControl />
    </div>

    <div v-if="etfLoading && etfs.length === 0" class="state-msg">載入 ETF 資料中…</div>
    <div v-else-if="etfError && etfs.length === 0" class="state-msg error">無法取得 ETF 資料：{{ etfError }}</div>
    <div v-else-if="etfs.length === 0" class="state-msg">暫無 ETF 資料</div>

    <template v-else>
      <div
        class="etf-grid"
        :style="gridStyle"
        @pointerdown="onPointerDown"
        @pointerup="onPointerUp"
      >
        <EtfCell
          v-for="(etf, idx) in pageEtfs"
          :key="etf.etf_id"
          :etf="etf"
          :rank="pageStart + idx + 1"
        />
        <div v-for="i in emptyCount" :key="`empty-${i}`" />
      </div>

      <Pager
        :page="page"
        :total="totalPages"
        :start="pageStart"
        :end="pageEnd"
        :count="filteredEtfs.length"
        @update:page="page = $event"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useBreakpoint } from '../composables/useBreakpoint'
import { MOBILE_DENSITY } from '../constants'
import EtfCell from './EtfCell.vue'
import DensityControl from './DensityControl.vue'
import Pager from './Pager.vue'

const store = useStockStore()
const { etfs, etfLoading, etfError, etfSortBy, gridSize, mobileDensity } = storeToRefs(store)
const { isMobile } = useBreakpoint()

const page = ref(0)
const selectedTypes = ref(new Set())

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

// Same as the stock grid: a poll keeps the page, a new listing resets it.
watch(etfSortBy, () => { page.value = 0 })
watch(pageSize,  () => { page.value = 0 })
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
  gap: 8px;
  min-height: 0;
}

.etf-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.etf-toolbar::-webkit-scrollbar { display: none; }

.toolbar-spacer { flex: 1; min-width: 8px; }

.etf-grid {
  flex: 1;
  display: grid;
  gap: 6px;
  min-height: 0;
}

@media (max-width: 768px) {
  .type-chip { min-height: 36px; }
}
</style>
