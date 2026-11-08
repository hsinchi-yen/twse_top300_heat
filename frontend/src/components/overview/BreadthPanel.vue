<template>
  <section class="panel breadth">
    <div>
      <h2 class="panel__title">市場寬度</h2>
      <p class="panel__hint">站上均線的股票比例。指數上漲但比例下滑，代表上漲集中在少數股票。樣本是今日熱門股，歷史走勢有倖存者偏差。</p>
    </div>

    <p v-if="!market.trendLoaded" class="empty">載入中…</p>
    <p v-else-if="!points.length" class="empty">累積足夠的每日收盤資料後顯示。</p>
    <template v-else>
      <LineChart :dates="dates" :series="breadthSeries" :height="150" :format="formatPercent" title="站上均線比例" />
      <h3 class="sub-title">等權指數（起始日 = 100）</h3>
      <LineChart :dates="dates" :series="indexSeries" :height="100" area :format="formatIndex" title="等權指數" />
    </template>

    <template v-if="historyDates.length >= 2">
      <h3 class="sub-title">評分中位數與「千張大戶退場」占比（每日評分紀錄）</h3>
      <LineChart :dates="historyDates" :series="historySeries" :height="120" :format="formatPercent" title="評分與警示走勢" />
      <p class="panel__hint">占比 = 觸發家數 ÷ 當日評分檔數；評分池每日變動，看占比不看家數。</p>
    </template>

    <template v-if="scored">
      <h3 class="sub-title">評分分布 <span class="num">（{{ scored }} 檔）</span></h3>
      <div class="sig-bar" role="img" :aria-label="signalAria">
        <i
          v-for="s in signalRows"
          :key="s.key"
          class="sig-seg"
          :style="{ flexGrow: s.count, background: `var(--sig-${s.key}-fg)` }"
          :title="`${s.label} ${s.count}`"
        />
      </div>
      <ul class="sig-legend">
        <li v-for="s in signalRows" :key="s.key">
          <i :style="{ background: `var(--sig-${s.key}-fg)` }" />
          {{ s.label }} <b class="num">{{ s.count }}</b>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useMarketStore } from '../../stores/marketStore'
import LineChart from '../charts/LineChart.vue'

const props = defineProps({
  summary: { type: Object, required: true },
})

const SIGNAL_LABELS = [
  ['strong_buy', '建議買進'],
  ['buy', '可分批買進'],
  ['watch', '觀察清單'],
  ['neutral', '不建議買進'],
  ['avoid', '高風險避開'],
]

const market = useMarketStore()

const points = computed(() => market.trend?.breadth ?? [])
const dates = computed(() => points.value.map(p => p.date))
const breadthSeries = computed(() => [
  { key: 'ma20', label: '站上月線', color: 'var(--series-2)', values: points.value.map(p => p.pct_above_ma20) },
  { key: 'ma60', label: '站上季線', color: 'var(--series-3)', values: points.value.map(p => p.pct_above_ma60) },
])
const indexSeries = computed(() => [
  { key: 'index', label: '等權指數', color: 'var(--series-1)', values: points.value.map(p => p.ew_index) },
])

const WHALE_EXIT = '千張大戶退場'
const history = computed(() => market.alertCounts?.summary ?? [])
const historyDates = computed(() => history.value.map(p => p.date))
const historySeries = computed(() => {
  const whale = (market.alertCounts?.alerts ?? []).find(a => a.name === WHALE_EXIT)
  return [
    { key: 'median', label: '評分中位數', color: 'var(--series-1)', values: history.value.map(p => p.median) },
    { key: 'whale', label: '大戶退場占比', color: 'var(--series-2)',
      values: whale ? whale.shares : history.value.map(() => 0) },
  ]
})

const scored = computed(() => props.summary.scored)
const signalRows = computed(() => SIGNAL_LABELS
  .map(([key, label]) => ({ key, label, count: props.summary.signalCounts[key] ?? 0 }))
  .filter(s => s.count > 0))
const signalAria = computed(() => signalRows.value.map(s => `${s.label} ${s.count} 檔`).join('，'))

const formatPercent = (v) => (v == null ? '—' : `${Math.round(v)}%`)
const formatIndex = (v) => (v == null ? '—' : v.toFixed(1))
</script>

<style scoped>
.breadth {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 14px 16px;
}

.empty { padding: 20px 0; font-size: 0.875rem; color: var(--text-secondary); }

.sub-title {
  margin-top: 2px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.sig-bar { display: flex; gap: 2px; height: 8px; border-radius: 4px; overflow: hidden; }
.sig-seg { display: block; flex-basis: 0; min-width: 2px; }

.sig-legend {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 2px 12px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}
.sig-legend li { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.sig-legend i { width: 8px; height: 8px; border-radius: 2px; }
.sig-legend b { color: var(--text-primary); font-weight: 600; }
</style>
