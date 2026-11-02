<template>
  <section class="panel compare">
    <h2 class="panel__title">比較</h2>

    <p v-if="loading" class="compare-msg">載入走勢…</p>
    <p v-else-if="failed" class="compare-msg">走勢暫時無法取得</p>
    <template v-else>
      <p v-if="selected.length < 2" class="compare-msg">再選一檔即可比較走勢，最多 3 檔。</p>
      <p v-else-if="!comparison.dates.length" class="compare-msg">這些股票沒有共同的交易日資料。</p>
      <template v-else>
        <h3 class="sub-title">近 6 個月走勢（共同起始日 = 100）</h3>
        <LineChart :dates="comparison.dates" :series="chartSeries" :height="180" :format="formatIndex" title="比較走勢" />
      </template>

      <div class="compare-scroll">
        <table class="compare-table">
          <thead>
            <tr>
              <th scope="col" />
              <th v-for="c in columns" :key="c.id" scope="col">
                <span class="compare-head">
                  <i class="compare-key" :style="{ background: c.color }" />
                  {{ c.name }}
                  <button class="icon-btn compare-remove" :aria-label="`移除 ${c.name}`" @click="emit('remove', c.id)">
                    <Icon name="close" :size="13" />
                  </button>
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.label" :data-row="row.key">
              <th scope="row">{{ row.label }}</th>
              <td v-for="(cell, i) in row.cells" :key="i" class="num" :class="cell.tone">{{ cell.text }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="compare-note">期間報酬以收盤價計算，未還原除權息。</p>
      <ResearchNote />
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useWatchlistStore } from '../stores/watchlistStore'
import { assessStock, rebasedComparison } from '../utils/analysis'
import { formatPct, formatPrice, formatSignedLots, pctClass } from '../utils/format'
import Icon from './Icon.vue'
import LineChart from './charts/LineChart.vue'
import ResearchNote from './ResearchNote.vue'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const WINDOW_DAYS = 132

const props = defineProps({
  // [{id, slot}]
  selected: { type: Array, required: true },
})
const emit = defineEmits(['remove'])

const { scores, signals } = storeToRefs(useStockStore())
const wl = useWatchlistStore()

const barsById = ref({})
const loading = ref(false)
const failed = ref(false)
let latest = 0

async function fetchBars(id) {
  const res = await fetch(`${API_BASE}/api/stocks/${encodeURIComponent(id)}/history?days=${WINDOW_DAYS}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()).bars ?? []
}

watch(() => props.selected.map(s => s.id), async (ids) => {
  const request = ++latest
  const missing = ids.filter(id => !barsById.value[id])
  failed.value = false
  // Also reached by deselecting mid-fetch: that request can no longer clear this.
  loading.value = missing.length > 0
  if (!missing.length) return
  try {
    const fetched = await Promise.all(missing.map(async id => [id, await fetchBars(id)]))
    if (request === latest) barsById.value = { ...barsById.value, ...Object.fromEntries(fetched) }
  } catch (err) {
    console.warn('[ComparePanel] history unavailable:', err.message)
    if (request === latest) failed.value = true
  } finally {
    if (request === latest) loading.value = false
  }
}, { immediate: true })

const comparison = computed(() => rebasedComparison(
  props.selected.map(s => ({ id: s.id, bars: barsById.value[s.id] ?? [] })),
))

const columns = computed(() => props.selected.map((s) => {
  const quote = wl.items.find(i => i.stock_id === s.id)?.quote ?? null
  const score = scores.value[s.id] ?? null
  const daily = signals.value[s.id] ?? null
  const values = comparison.value.series.find(x => x.id === s.id)?.values ?? []
  return {
    id: s.id,
    name: quote?.name ?? s.id,
    color: `var(--series-${s.slot})`,
    quote,
    score,
    daily,
    assessment: assessStock({ stock: quote, score, daily }),
    windowReturn: values.length ? values[values.length - 1] - 100 : null,
  }
}))

const chartSeries = computed(() => columns.value.map((c) => ({
  key: c.id,
  label: c.name,
  color: c.color,
  values: comparison.value.series.find(s => s.id === c.id)?.values ?? [],
})))

const text = (value) => ({ text: value ?? '—', tone: '' })

const rows = computed(() => {
  const dimension = (key, label) => ({
    key,
    label,
    cells: columns.value.map((c) => {
      const score = c.assessment.dimensions.find(d => d.key === key).score
      return text(score === null ? null : Math.round(score))
    }),
  })
  return [
    { key: 'composite', label: '綜合分', cells: columns.value.map(c => text(c.assessment.composite)) },
    { key: 'stance', label: '狀態', cells: columns.value.map(c => text(c.assessment.stance.label)) },
    dimension('quality', '基本面'),
    dimension('trend', '趨勢'),
    dimension('flow', '籌碼'),
    dimension('value', '評價'),
    { key: 'price', label: '現價', cells: columns.value.map(c => text(formatPrice(c.quote?.close_price))) },
    {
      key: 'return',
      label: '期間報酬',
      cells: columns.value.map(c => ({ text: formatPct(c.windowReturn, 1), tone: pctClass(c.windowReturn) })),
    },
    { key: 'pe', label: 'P/E', cells: columns.value.map(c => text(c.score?.pe?.current)) },
    { key: 'inst', label: '法人 5 日（張）', cells: columns.value.map(c => text(formatSignedLots(c.daily?.inst_net_5d))) },
  ]
})

const formatIndex = (v) => (v == null ? '—' : v.toFixed(1))
</script>

<style scoped>
.compare {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
  padding: 14px 16px;
}

.compare-msg { font-size: 0.8125rem; color: var(--text-muted); }
.compare-note { font-size: 0.75rem; color: var(--text-muted); }

.sub-title { font-size: 0.75rem; font-weight: 500; color: var(--text-secondary); }

.compare-scroll { overflow-x: auto; }

.compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.compare-table th,
.compare-table td {
  padding: 5px 8px;
  border-top: 1px solid var(--border-subtle);
  text-align: right;
  white-space: nowrap;
}

.compare-table thead th { border-top: none; font-weight: 600; color: var(--text-primary); }
.compare-table tbody th { font-weight: 400; color: var(--text-secondary); text-align: left; padding-left: 0; }

.compare-head { display: inline-flex; align-items: center; gap: 6px; }
.compare-key { width: 14px; height: 2px; border-radius: 1px; }
.compare-remove { width: 22px; height: 22px; }
</style>
