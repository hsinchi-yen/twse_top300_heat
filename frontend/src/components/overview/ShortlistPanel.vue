<template>
  <section class="panel shortlist">
    <header class="panel-head">
      <div>
        <h2 class="panel__title">研究候選清單</h2>
        <p class="panel__hint">依綜合分排序，已排除排雷 2 項以上與資料不足者</p>
      </div>
      <span v-if="rows.length" class="list-count num">{{ rows.length }} 檔</span>
    </header>

    <p v-if="!scoresLoaded" class="empty">載入評分中…</p>
    <p v-else-if="!scoreCount" class="empty">尚無評分資料，交易日後凌晨 03:00 計算完成後顯示。</p>
    <p v-else-if="!signalCount" class="empty">盤後指標尚未產生，交易日後凌晨 03:00 計算完成後顯示。</p>
    <p v-else-if="!rows.length" class="empty">目前沒有股票同時滿足條件。沒有候選也是一種資訊。</p>

    <ol v-else class="rows">
      <li v-for="(row, i) in rows" :key="row.stock.stock_id" class="row">
        <button class="row-open" @click="ui.openStock(row.stock.stock_id)">
          <span class="row-rank num">{{ i + 1 }}</span>
          <span class="row-stock">
            <span class="row-name">{{ row.stock.name }}</span>
            <span class="row-meta num">{{ row.stock.stock_id }} · {{ row.stock.sector }}</span>
          </span>
          <span class="row-price num">
            <span>{{ formatPrice(row.stock.close_price) }}</span>
            <span :class="pctClass(row.stock.price_change_pct)">{{ formatPct(row.stock.price_change_pct) }}</span>
          </span>
          <span class="row-score">
            <span class="score-value num">{{ row.assessment.composite }}</span>
            <span class="score-bar"><span class="score-fill" :style="{ width: `${row.assessment.composite}%` }" /></span>
          </span>
          <span class="row-stance">
            <span class="tag" :data-stance="row.assessment.stance.key">{{ row.assessment.stance.label }}</span>
          </span>
          <span class="row-why">
            <span v-if="row.assessment.strengths[0]">{{ row.assessment.strengths[0] }}</span>
            <span v-if="row.assessment.cautions[0]" class="why-caution">{{ row.assessment.cautions[0] }}</span>
          </span>
        </button>
        <button
          class="icon-btn row-pin"
          :class="{ pinned: wl.isPinned(row.stock.stock_id) }"
          :title="wl.isPinned(row.stock.stock_id) ? '移出自選' : '加入自選'"
          :aria-pressed="wl.isPinned(row.stock.stock_id)"
          @click="wl.toggle(row.stock.stock_id)"
        ><Icon name="star" :size="16" /></button>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useStockStore } from '../../stores/stockStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { useUiStore } from '../../stores/uiStore'
import { shortlist } from '../../utils/analysis'
import { formatPct, formatPrice, pctClass } from '../../utils/format'
import Icon from '../Icon.vue'

const { stockPool, scores, signals, scoresLoaded } = storeToRefs(useStockStore())
const wl = useWatchlistStore()
const ui = useUiStore()

const rows = computed(() => shortlist(stockPool.value, { scores: scores.value, signals: signals.value }))
const scoreCount = computed(() => Object.keys(scores.value).length)
// The list needs both sources: "no candidates" must not stand in for "no data yet".
const signalCount = computed(() => Object.keys(signals.value).length)
</script>

<style scoped>
.shortlist {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 14px 8px 8px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 0 8px 8px;
}

.list-count { font-size: 0.8125rem; color: var(--text-muted); white-space: nowrap; }

.empty {
  padding: 28px 12px;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.rows { list-style: none; }

.row {
  display: flex;
  align-items: center;
  border-top: 1px solid var(--border-subtle);
}

.row-open {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: 22px minmax(112px, 1.1fr) 82px 112px 74px minmax(0, 2fr);
  align-items: center;
  gap: 10px;
  padding: 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-primary);
  text-align: left;
}
.row-open:hover { background: var(--hover-wash); }

.row-rank { font-size: 0.8125rem; color: var(--text-muted); }

.row-stock { display: flex; flex-direction: column; min-width: 0; }
.row-name { font-size: 0.9375rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.row-meta { font-size: 0.75rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.row-price { display: flex; flex-direction: column; align-items: flex-end; font-size: 0.8125rem; }

.row-score { display: flex; align-items: center; gap: 8px; }
.score-value { font-size: 1.0625rem; font-weight: 700; min-width: 1.5em; }
.score-bar { flex: 1; height: 5px; border-radius: 3px; background: var(--chip-bg); overflow: hidden; }
.score-fill { display: block; height: 100%; border-radius: 3px; background: var(--accent); }

.row-why {
  display: flex;
  flex-direction: column;
  min-width: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
}
.row-why span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.why-caution { color: var(--chip-warn-fg); }

.row-pin.pinned { color: var(--sig-strong_buy-fg); }
.row-pin.pinned :deep(path) { fill: currentColor; }

@media (max-width: 1100px) {
  .row-open {
    grid-template-columns: 22px minmax(0, 1fr) 76px 64px;
    grid-template-areas:
      "rank stock price score"
      ".    why   why   stance";
    gap: 2px 8px;
  }
  .row-rank { grid-area: rank; }
  .row-stock { grid-area: stock; }
  .row-price { grid-area: price; }
  .row-score { grid-area: score; justify-content: flex-end; }
  .score-bar { display: none; }
  .row-stance { grid-area: stance; justify-self: end; }
  .row-why { grid-area: why; }
}
</style>
