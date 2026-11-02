<template>
  <section class="panel setups">
    <header class="panel-head">
      <div>
        <h2 class="panel__title">技術型態歷史驗證</h2>
        <p class="panel__hint">出現訊號後持有固定天數的報酬，與全體基準比較</p>
      </div>
      <div class="segmented" role="group" aria-label="持有天數">
        <button
          v-for="h in HORIZONS"
          :key="h"
          class="segmented__item"
          :class="{ active: market.horizon === h }"
          :aria-pressed="market.horizon === h"
          @click="market.loadBacktest(h)"
        >{{ h }} 日</button>
      </div>
    </header>

    <p v-if="!data" class="empty">{{ market.backtestFailed ? '暫時無法取得' : '載入中…' }}</p>
    <p v-else-if="!data.periods" class="empty">歷史資料不足，累積更多交易日後顯示。</p>
    <template v-else>
      <table class="setup-table">
        <thead>
          <tr>
            <th scope="col">型態</th>
            <th scope="col" class="num-col">平均報酬</th>
            <th scope="col" class="num-col">超額</th>
            <th scope="col" class="num-col">勝過基準</th>
            <th scope="col" class="num-col hide-narrow">上漲比例</th>
            <th scope="col" class="num-col hide-narrow">最差一期</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in data.setups" :key="s.key" :data-setup="s.key">
            <td class="setup-name">{{ s.label }}</td>
            <template v-if="s.periods">
              <td class="num-col num">{{ formatPct(s.avg_ret, 1) }}</td>
              <td class="num-col num" :class="pctClass(s.avg_excess)">{{ formatPct(s.avg_excess, 1) }}</td>
              <td class="num-col num">{{ s.beat_periods }} / {{ s.periods }} 期</td>
              <td class="num-col num hide-narrow">{{ s.win_rate.toFixed(0) }}%</td>
              <td class="num-col num hide-narrow">{{ formatPct(s.worst_period_ret, 1) }}</td>
            </template>
            <td v-else colspan="5" class="num-col thin">樣本不足</td>
          </tr>
          <tr class="baseline-row">
            <td class="setup-name">全體基準</td>
            <td class="num-col num">{{ formatPct(data.baseline.avg_ret, 1) }}</td>
            <td class="num-col">—</td>
            <td class="num-col num">{{ data.periods }} 期</td>
            <td class="num-col num hide-narrow">{{ data.baseline.win_rate.toFixed(0) }}%</td>
            <td class="num-col hide-narrow">—</td>
          </tr>
        </tbody>
      </table>
      <p class="caveat">
        以訊號次一交易日收盤進場計算。僅一年資料、期數少，差距可能只是雜訊。樣本是今日熱門股，存在倖存者偏差，報酬因此偏高；未含交易成本與除權息。超額只計該型態有樣本的期數，因此不等於平均報酬減全體基準。
        買進評分本身無法驗證：系統只保留 7 次評分紀錄。
      </p>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useMarketStore } from '../../stores/marketStore'
import { formatPct, pctClass } from '../../utils/format'

const HORIZONS = [5, 20, 60]

const market = useMarketStore()
// Only numbers for the selected horizon may sit under that label.
const data = computed(() => (market.backtest?.horizon === market.horizon ? market.backtest : null))
</script>

<style scoped>
.setups {
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

.setup-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.setup-table th {
  padding: 4px 6px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-muted);
  text-align: left;
  white-space: nowrap;
}

.setup-table td {
  padding: 6px;
  border-top: 1px solid var(--border-subtle);
}

.setup-table th:first-child,
.setup-table td:first-child { padding-left: 0; }

.setup-name { font-weight: 500; white-space: nowrap; }
.num-col { text-align: right !important; white-space: nowrap; }
.thin { color: var(--text-muted); }
.baseline-row td { color: var(--text-secondary); }

.caveat { font-size: 0.75rem; color: var(--text-muted); }

@media (max-width: 640px) {
  .hide-narrow { display: none; }
}
</style>
