<template>
  <div class="etf-cell" :data-tier="etf.color_tier" :style="cellStyle" :title="tooltipText">
    <div class="cell-top">
      <span class="cell-rank num">#{{ rank }}</span>
      <span class="cell-type" :data-type="etf.etf_type">{{ etf.etf_type }}</span>
      <span v-if="etf.asset_scale != null" class="cell-scale num">{{ formatScale(etf.asset_scale) }}</span>
    </div>

    <div class="cell-name">
      <span class="cell-name-text">{{ etf.name }}</span>
      <span class="cell-code num">{{ etf.etf_id }}</span>
    </div>

    <div class="cell-metric">
      <span class="cell-turnover num">{{ turnoverDisplay }}</span>
      <span class="cell-fee num">{{ feeLabel }}</span>
    </div>

    <div class="cell-bottom">
      <span class="cell-price num">{{ etf.close_price ? formatPrice(etf.close_price) : '' }}</span>
      <span class="cell-premium num" :title="premiumTitle">{{ premiumLabel }}</span>
      <span class="cell-pct num" :class="pctClass(etf.price_change_pct)">{{ formatPct(etf.price_change_pct) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { tierToColor, tierToBorder } from '../utils/colorTier'
import { formatPct, formatPrice, pctClass } from '../utils/format'

const props = defineProps({
  etf:  { type: Object, required: true },
  rank: { type: Number, default: 0 },
})

const cellStyle = computed(() => ({
  backgroundColor: tierToColor(props.etf.color_tier),
  borderColor: tierToBorder(props.etf.color_tier),
}))

// 成交量週轉率：有值顯示%，無值(週末)顯示成交量作參考
const turnoverDisplay = computed(() => {
  if (props.etf.turnover_rate != null) return `週轉 ${props.etf.turnover_rate.toFixed(3)}%`
  const vol = props.etf.volume
  if (vol == null) return '—'
  if (vol >= 100_000_000) return `${(vol / 100_000_000).toFixed(1)}億股`
  if (vol >= 10_000_000)  return `${(vol / 10_000_000).toFixed(1)}千萬股`
  if (vol >= 10_000)      return `${(vol / 10_000).toFixed(0)}萬股`
  return `${vol}股`
})

const feeLabel = computed(() => (
  props.etf.management_fee != null ? `費 ${props.etf.management_fee}%` : ''
))

const premiumLabel = computed(() => {
  const p = props.etf.premium_discount
  return p == null ? '' : `${p > 0 ? '溢' : p < 0 ? '折' : '平'} ${Math.abs(p).toFixed(2)}%`
})

const premiumTitle = computed(() => (
  props.etf.nav != null ? `淨值 ${props.etf.nav}` : ''
))

const tooltipText = computed(() => {
  const e = props.etf
  const portfolio = e.portfolio_turnover != null ? `${e.portfolio_turnover.toFixed(0)}%/年` : '—'
  return [
    `#${props.rank} ${e.etf_id} ${e.name}`,
    e.etf_type,
    `規模 ${formatScale(e.asset_scale)}`,
    `管理費 ${e.management_fee != null ? `${e.management_fee}%/年` : '—'}`,
    `持股週轉率 ${portfolio}`,
  ].join('｜')
})

function formatScale(v) {
  if (v == null) return '—'
  if (v >= 10000) return `${(v / 10000).toFixed(1)}兆`
  return `${v.toFixed(0)}億`
}
</script>

<style scoped>
.etf-cell {
  container-type: inline-size;
  width: 100%;
  height: 100%;
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 2px;
  padding: 8px 10px;
  overflow: hidden;
  border: 1px solid transparent;
}

.cell-top {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-shrink: 0;
}

.cell-rank {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.cell-type {
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
/* 槓桿 / 反向 are not long-term holdings; they get the one caution colour. */
.cell-type[data-type="槓桿"],
.cell-type[data-type="反向"] { color: var(--warn); font-weight: 600; }

.cell-scale {
  margin-left: auto;
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

.cell-name {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  font-size: clamp(0.9rem, 1.2vw, 1.05rem);
  font-weight: 600;
  line-height: 1.25;
  color: var(--text-primary);
}

.cell-name-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.cell-code {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.cell-metric {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.cell-bottom {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 4px;
  flex-shrink: 0;
}

.cell-price {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
}

.cell-premium {
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.cell-pct {
  font-size: 0.9rem;
  font-weight: 700;
  white-space: nowrap;
}

@container (max-width: 190px) {
  .cell-fee, .cell-premium { display: none; }
}

@media (max-height: 768px) {
  .etf-cell { padding: 5px 8px; gap: 1px; }
}
</style>
