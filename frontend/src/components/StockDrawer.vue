<template>
  <div v-if="stockId" class="drawer-layer">
    <div class="drawer-scrim" @click="ui.closeStock()" />
    <aside
      ref="dialog"
      class="drawer"
      role="dialog"
      aria-modal="true"
      :aria-label="`${quote?.name ?? stockId} 個股分析`"
      tabindex="-1"
    >
      <header class="drawer-head">
        <div class="head-title">
          <h2 class="head-name">{{ quote?.name ?? stockId }}</h2>
          <span class="head-meta num">{{ stockId }}<template v-if="quote?.sector"> · {{ quote.sector }}</template></span>
        </div>
        <button
          class="icon-btn drawer-pin"
          :class="{ pinned }"
          :title="pinned ? '移出自選' : '加入自選'"
          :aria-pressed="pinned"
          @click="wl.toggle(stockId)"
        ><Icon name="star" /></button>
        <button class="icon-btn drawer-close" aria-label="關閉" @click="ui.closeStock()"><Icon name="close" /></button>
      </header>

      <div class="drawer-body">
        <div v-if="quote" class="price-row">
          <span class="price-now">{{ formatPrice(quote.close_price) }}</span>
          <span class="price-pct num" :class="pctClass(quote.price_change_pct)">{{ formatPct(quote.price_change_pct) }}</span>
          <span class="price-turnover num">週轉率 {{ formatTurnover(quote.turnover_rate) }}</span>
          <span class="price-turnover num">成交 {{ formatLots(quote.volume) }}</span>
        </div>

        <section class="block verdict">
          <div class="verdict-head">
            <div class="composite">
              <span class="composite-value">{{ assessment.composite ?? '—' }}</span>
              <span class="composite-label">綜合分</span>
            </div>
            <div class="verdict-text">
              <span class="tag stance-tag" :data-stance="assessment.stance.key">{{ assessment.stance.label }}</span>
              <p class="stance-hint">{{ assessment.stance.hint }}</p>
            </div>
          </div>

          <ul class="dims">
            <li v-for="d in assessment.dimensions" :key="d.key" class="dim" :data-dim="d.key">
              <span class="dim-label">{{ d.label }}</span>
              <span class="dim-bar"><span class="dim-fill" :style="{ width: `${d.score ?? 0}%` }" /></span>
              <span class="dim-value num">{{ d.score === null ? '無資料' : Math.round(d.score) }}</span>
            </li>
          </ul>

          <div v-if="assessment.strengths.length || assessment.cautions.length" class="reasons">
            <ul v-if="assessment.strengths.length" class="reason-list reason-list--good">
              <li v-for="r in assessment.strengths" :key="r">{{ r }}</li>
            </ul>
            <ul v-if="assessment.cautions.length" class="reason-list reason-list--warn">
              <li v-for="r in assessment.cautions" :key="r">{{ r }}</li>
            </ul>
          </div>
        </section>

        <section class="block">
          <div class="block-head">
            <h3 class="panel__title">價格走勢</h3>
            <div class="segmented" role="group" aria-label="期間">
              <button
                v-for="r in RANGES"
                :key="r.days"
                class="segmented__item"
                :class="{ active: rangeDays === r.days }"
                :aria-pressed="rangeDays === r.days"
                @click="rangeDays = r.days"
              >{{ r.label }}</button>
            </div>
          </div>

          <p v-if="loading" class="block-msg">載入走勢…</p>
          <p v-else-if="failed" class="block-msg">走勢暫時無法取得</p>
          <p v-else-if="!visibleBars.length" class="block-msg">尚無歷史資料（交易日後凌晨 03:00 更新）</p>
          <template v-else>
            <LineChart
              :key="`price-${rangeDays}`"
              :dates="barDates"
              :series="priceSeries"
              :height="210"
              :format="formatPrice"
              title="收盤價與均線"
            />
            <h4 class="sub-title">成交量（張）</h4>
            <ColumnChart
              :key="`vol-${rangeDays}`"
              :dates="barDates"
              :values="volumeLots"
              label="成交量（張）"
              :height="96"
              :format="formatCount"
            />
            <p v-if="rangeMove !== null" class="block-foot num">
              區間漲跌 <span :class="pctClass(rangeMove)">{{ formatPct(rangeMove, 1) }}</span>
              · 收盤未還原除權息
            </p>
          </template>
        </section>

        <section v-if="flows.length" class="block">
          <h3 class="panel__title">法人動向</h3>
          <dl class="tiles">
            <div><dt>外資（當日）</dt><dd class="num">{{ formatSignedLots(daily?.foreign_net_1d) }}</dd></div>
            <div><dt>投信（當日）</dt><dd class="num">{{ formatSignedLots(daily?.trust_net_1d) }}</dd></div>
            <div><dt>近 5 日合計</dt><dd class="num">{{ formatSignedLots(daily?.inst_net_5d) }}</dd></div>
            <div><dt>連續</dt><dd class="num">{{ streakLabel }}</dd></div>
          </dl>
          <h4 class="sub-title">外資＋投信每日買賣超（張）</h4>
          <ColumnChart
            :dates="flows.map(f => f.date)"
            :values="flowNets"
            label="外資＋投信（張）"
            tone="direction"
            :height="120"
            :format="formatSignedLots"
          />
        </section>

        <section v-if="scorePoints.length >= 2" class="block">
          <h3 class="panel__title">通過率走勢</h3>
          <p class="panel__hint">保留最近 {{ scorePoints.length }} 次評分</p>
          <LineChart
            :dates="scorePoints.map(p => p.date)"
            :series="scoreSeries"
            :height="110"
            area
            :format="formatRate"
            title="基本面通過率"
          />
        </section>

        <section class="block">
          <h3 class="panel__title">部位試算</h3>
          <p class="panel__hint">依你能承受的虧損回推部位上限，這是風險上限，不是買進建議。</p>
          <PositionSizer
            :key="stockId"
            :price="quote?.close_price ?? null"
            :ma60="daily?.ma60 ?? null"
            :avg-volume="daily?.avg_volume_5d ?? null"
          />
        </section>

        <section class="block">
          <h3 class="panel__title">基本面明細</h3>
          <ScoreDetail :key="stockId" :stock-id="stockId" />
        </section>

        <ResearchNote />
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, ref, toRef } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../stores/stockStore'
import { useWatchlistStore } from '../stores/watchlistStore'
import { useUiStore } from '../stores/uiStore'
import { useDialog } from '../composables/useDialog'
import { useStockHistory } from '../composables/useStockHistory'
import { assessStock } from '../utils/analysis'
import { formatLots, formatPct, formatPrice, formatSignedLots, formatTurnover, pctClass } from '../utils/format'
import Icon from './Icon.vue'
import LineChart from './charts/LineChart.vue'
import ColumnChart from './charts/ColumnChart.vue'
import PositionSizer from './PositionSizer.vue'
import ScoreDetail from './ScoreDetail.vue'
import ResearchNote from './ResearchNote.vue'

const RANGES = [
  { label: '1 月', days: 22 },
  { label: '3 月', days: 66 },
  { label: '6 月', days: 132 },
  { label: '1 年', days: 260 },
]

const store = useStockStore()
const { stockPool, scores, signals } = storeToRefs(store)
const wl = useWatchlistStore()
const ui = useUiStore()

const stockId = toRef(ui, 'selectedStockId')
const isOpen = computed(() => Boolean(stockId.value))
const { dialog } = useDialog(isOpen, () => ui.closeStock())
const { bars, flows, scorePoints, loading, failed } = useStockHistory(stockId)

const rangeDays = ref(132)

const quote = computed(() => (
  stockPool.value.find(s => s.stock_id === stockId.value)
  ?? wl.items.find(i => i.stock_id === stockId.value)?.quote
  ?? null
))
const score = computed(() => scores.value[stockId.value] ?? null)
const daily = computed(() => signals.value[stockId.value] ?? null)
const pinned = computed(() => wl.isPinned(stockId.value))

const assessment = computed(() => assessStock({ stock: quote.value, score: score.value, daily: daily.value }))

const visibleBars = computed(() => bars.value.slice(-rangeDays.value))
const barDates = computed(() => visibleBars.value.map(b => b.date))
const volumeLots = computed(() => visibleBars.value.map(b => (b.volume == null ? null : Math.round(b.volume / 1000))))
const priceSeries = computed(() => [
  { key: 'close', label: '收盤', color: 'var(--series-1)', values: visibleBars.value.map(b => b.close) },
  { key: 'ma20', label: '月線', color: 'var(--series-2)', values: visibleBars.value.map(b => b.ma20) },
  { key: 'ma60', label: '季線', color: 'var(--series-3)', values: visibleBars.value.map(b => b.ma60) },
])

const rangeMove = computed(() => {
  const list = visibleBars.value
  if (list.length < 2) return null
  return (list[list.length - 1].close / list[0].close - 1) * 100
})

const flowNets = computed(() => flows.value.map(f => (
  f.foreign_net == null && f.trust_net == null ? null : (f.foreign_net ?? 0) + (f.trust_net ?? 0)
)))

const streakLabel = computed(() => {
  const s = daily.value?.inst_streak
  if (s == null) return '—'
  if (s === 0) return '無'
  return `${s > 0 ? '連買' : '連賣'} ${Math.abs(s)} 日`
})

const scoreSeries = computed(() => [
  { key: 'pass', label: '通過率', color: 'var(--series-1)', values: scorePoints.value.map(p => p.pass_rate) },
])

const formatCount = (v) => (v == null ? '—' : Math.round(v).toLocaleString('en-US'))
const formatRate = (v) => (v == null ? '—' : `${Math.round(v)}%`)
</script>

<style scoped>
.drawer-layer {
  position: fixed;
  inset: 0;
  z-index: 300;
}

.drawer-scrim {
  position: absolute;
  inset: 0;
  background: var(--scrim);
  animation: fade-in 0.15s ease-out;
}

.drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(620px, 100%);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-left: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
  outline: none;
  animation: slide-in 0.18s ease-out;
}

@keyframes fade-in { from { opacity: 0; } }
@keyframes slide-in { from { transform: translateX(24px); opacity: 0; } }

.drawer-head {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 14px 16px 10px 20px;
  border-bottom: 1px solid var(--border-subtle);
}

.head-title { flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 10px; }
.head-name { font-size: 1.25rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.head-meta { font-size: 0.8125rem; color: var(--text-secondary); white-space: nowrap; }

.drawer-pin.pinned { color: var(--sig-strong_buy-fg); }
.drawer-pin.pinned :deep(path) { fill: currentColor; }

.drawer-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.price-row { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; }
.price-now { font-size: 2rem; font-weight: 700; line-height: 1.1; }
.price-pct { font-size: 1.0625rem; font-weight: 600; }
.price-turnover { font-size: 0.8125rem; color: var(--text-secondary); }

.block { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.block-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.block-msg { padding: 16px 0; font-size: 0.8125rem; color: var(--text-muted); }
.block-foot { font-size: 0.75rem; color: var(--text-muted); }
.sub-title { margin-top: 4px; font-size: 0.75rem; font-weight: 500; color: var(--text-secondary); }

.verdict {
  gap: 12px;
  padding: 14px;
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
  border: 1px solid var(--border-subtle);
}

.verdict-head { display: flex; align-items: center; gap: 14px; }

.composite { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; min-width: 56px; }
.composite-value { font-size: 2.25rem; font-weight: 700; line-height: 1; }
.composite-label { margin-top: 2px; font-size: 0.75rem; color: var(--text-muted); }

.verdict-text { min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
.stance-hint { font-size: 0.8125rem; color: var(--text-secondary); }

.dims { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.dim {
  display: grid;
  grid-template-columns: 3.2em 1fr 3.4em;
  align-items: center;
  gap: 8px;
  font-size: 0.8125rem;
}
.dim-label { color: var(--text-secondary); }
.dim-bar { height: 6px; border-radius: 3px; background: var(--chip-bg); overflow: hidden; }
.dim-fill { display: block; height: 100%; border-radius: 3px; background: var(--accent); }
.dim-value { text-align: right; color: var(--text-primary); font-size: 0.75rem; }

.reasons { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.reason-list { list-style: none; display: flex; flex-direction: column; gap: 3px; font-size: 0.8125rem; }
.reason-list li { position: relative; padding-left: 14px; color: var(--text-primary); }
.reason-list li::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 0.55em;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.reason-list--good li::before { background: var(--accent); }
.reason-list--warn li::before { background: var(--warn); border-radius: 1px; }

.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.tiles dt { font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap; }
.tiles dd { font-size: 0.9375rem; font-weight: 600; }

@media (max-width: 480px) {
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .drawer-body { padding: 12px 14px 20px; }
}
</style>
