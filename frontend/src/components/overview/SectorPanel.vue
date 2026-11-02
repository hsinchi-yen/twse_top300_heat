<template>
  <section class="panel sectors">
    <header class="panel-head">
      <div>
        <h2 class="panel__title">族群輪動</h2>
        <p class="panel__hint">族群內個股漲跌的中位數，避免被單一飆股拉高</p>
      </div>
      <div class="segmented" role="group" aria-label="族群期間">
        <button
          v-for="m in METRICS"
          :key="m.key"
          class="segmented__item"
          :class="{ active: metric === m.key }"
          :aria-pressed="metric === m.key"
          :disabled="m.needsTrend && !hasTrend"
          @click="metric = m.key"
        >{{ m.label }}</button>
      </div>
    </header>

    <p v-if="!rows.length" class="empty">尚無族群資料</p>
    <table v-else class="sector-table">
      <thead>
        <tr>
          <th scope="col">族群</th>
          <th scope="col" class="bar-col">{{ metricLabel }}</th>
          <th scope="col" class="num-col">月線上</th>
          <th scope="col" class="num-col hide-narrow">法人 5 日（張）</th>
          <th scope="col" class="num-col hide-narrow">平均通過率</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in visibleRows" :key="row.name">
          <td>
            <button class="sector-open" :title="`查看${row.name}的個股`" @click="openSector(row.name)">
              <span class="sector-name">{{ row.name }}</span>
              <span class="sector-count num">{{ row.count }}</span>
            </button>
          </td>
          <td class="bar-col">
            <span class="bar-wrap">
              <span class="bar-track">
                <span
                  v-if="row.value != null"
                  class="bar-fill"
                  :class="row.value >= 0 ? 'bar-fill--up' : 'bar-fill--down'"
                  :style="barStyle(row.value)"
                />
              </span>
              <span class="bar-value num" :class="pctClass(row.value)">{{ formatPct(row.value, 1) }}</span>
            </span>
          </td>
          <td class="num-col num">{{ row.pctAboveMa20 == null ? '—' : `${Math.round(row.pctAboveMa20)}%` }}</td>
          <td class="num-col num hide-narrow">{{ formatSignedLots(row.instNet) }}</td>
          <td class="num-col num hide-narrow">{{ row.avgPassRate == null ? '—' : `${Math.round(row.avgPassRate)}%` }}</td>
        </tr>
      </tbody>
    </table>

    <p v-if="hasTrend" class="panel__hint">多日報酬的樣本是今日熱門股，有倖存者偏差，且未還原除權息。</p>

    <button v-if="rows.length > LIMIT" class="btn more-btn" @click="expanded = !expanded">
      {{ expanded ? '收合' : `顯示全部 ${rows.length} 個族群` }}
    </button>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../../stores/stockStore'
import { useMarketStore } from '../../stores/marketStore'
import { useFilterStore } from '../../stores/filterStore'
import { sectorSnapshot } from '../../utils/analysis'
import { formatPct, formatSignedLots, pctClass } from '../../utils/format'

const METRICS = [
  { key: 'today', label: '今日', needsTrend: false },
  { key: 'ret_5d', label: '5 日', needsTrend: true },
  { key: 'ret_20d', label: '20 日', needsTrend: true },
  { key: 'ret_60d', label: '60 日', needsTrend: true },
]
const LIMIT = 10

const store = useStockStore()
const { stockPool, scores, heatmapMode } = storeToRefs(store)
const market = useMarketStore()
const filters = useFilterStore()

function openSector(name) {
  filters.setSector(name)
  store.setMode(heatmapMode.value)
}

const metric = ref('today')
const expanded = ref(false)

const trendRows = computed(() => market.trend?.sectors ?? [])
const hasTrend = computed(() => trendRows.value.length > 0)
const metricLabel = computed(() => METRICS.find(m => m.key === metric.value).label)

const rows = computed(() => {
  const trend = new Map(trendRows.value.map(r => [r.name, r]))
  const merged = sectorSnapshot(stockPool.value, { scores: scores.value }).map((live) => {
    const t = trend.get(live.name)
    return {
      name: live.name,
      count: live.count,
      avgPassRate: live.avgPassRate,
      pctAboveMa20: t?.pct_above_ma20 ?? null,
      instNet: t?.inst_net_5d ?? null,
      value: metric.value === 'today' ? live.medianChange : t?.[metric.value] ?? null,
    }
  })
  return merged.sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity))
})

const visibleRows = computed(() => (expanded.value ? rows.value : rows.value.slice(0, LIMIT)))

const scale = computed(() => Math.max(0.01, ...rows.value.map(r => Math.abs(r.value ?? 0))))

function barStyle(value) {
  const share = (Math.abs(value) / scale.value) * 50
  return value >= 0
    ? { left: '50%', width: `${share}%` }
    : { right: '50%', width: `${share}%` }
}
</script>

<style scoped>
.sectors {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 14px 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.empty { padding: 20px 0; font-size: 0.875rem; color: var(--text-secondary); }

.sector-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.sector-table th {
  padding: 4px 6px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-muted);
  text-align: left;
  white-space: nowrap;
}

.sector-table td {
  padding: 5px 6px;
  border-top: 1px solid var(--border-subtle);
}

.sector-table th:first-child,
.sector-table td:first-child { padding-left: 0; }

.num-col { text-align: right !important; white-space: nowrap; color: var(--text-secondary); }
.bar-col { width: 40%; }

.sector-open {
  padding: 0;
  border: none;
  background: none;
  color: var(--text-primary);
  text-align: left;
  white-space: nowrap;
}
.sector-open:hover .sector-name { color: var(--accent); }
.sector-name { font-weight: 500; }
.sector-count { margin-left: 6px; font-size: 0.75rem; color: var(--text-muted); }

.bar-wrap { display: flex; align-items: center; gap: 8px; }
.bar-track { position: relative; flex: 1; height: 8px; }
.bar-track::after {
  content: '';
  position: absolute;
  left: 50%;
  top: -2px;
  bottom: -2px;
  width: 1px;
  background: var(--chart-axis);
}
.bar-fill { position: absolute; top: 0; bottom: 0; }
.bar-fill--up { background: var(--pct-up); border-radius: 0 4px 4px 0; }
.bar-fill--down { background: var(--pct-down); border-radius: 4px 0 0 4px; }
.bar-value { min-width: 3.6em; text-align: right; }

.more-btn { align-self: flex-start; }

@media (max-width: 640px) {
  .hide-narrow { display: none; }
  .bar-col { width: 55%; }
}
</style>
