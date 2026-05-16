<template>
  <div
    class="etf-cell"
    :data-tier="etf.color_tier"
    :style="cellStyle"
    :title="tooltipText"
  >
    <!-- hover tooltip overlay -->
    <div class="etf-tooltip">
      <div class="tooltip-row">
        <span class="tooltip-label">資產規模</span>
        <span class="tooltip-val">{{ formatScale(etf.asset_scale) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">溢折價</span>
        <span class="tooltip-val" :class="premiumClass">{{ formatPremium(etf.premium_discount) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">管理費</span>
        <span class="tooltip-val">{{ etf.management_fee != null ? `${etf.management_fee}%/年` : '—' }}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">持股週轉率</span>
        <span class="tooltip-val tooltip-val--portfolio">{{ formatPortfolioTurnover(etf.portfolio_turnover) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">漲跌幅</span>
        <span class="tooltip-val" :class="pctClass">{{ formatPct(etf.price_change_pct) }}</span>
      </div>
    </div>

    <!-- 頂部：排名 | ETF類型 | 資產規模 -->
    <div class="cell-top">
      <span class="cell-rank mono">#{{ rank }}</span>
      <span class="cell-type-badge" :data-type="etf.etf_type">{{ etf.etf_type }}</span>
      <span class="cell-scale mono">{{ formatScale(etf.asset_scale) }}</span>
    </div>

    <!-- 代號 + 現價 -->
    <div class="cell-meta">
      <span class="cell-code mono">{{ etf.etf_id }}</span>
      <span class="cell-price mono" v-if="etf.close_price">{{ formatPrice(etf.close_price) }}</span>
    </div>

    <!-- 名稱 -->
    <div class="cell-name">{{ etf.name }}</div>

    <!-- 底部：持股週轉率(左) + 成交量週轉率(右) -->
    <div class="cell-bottom">
      <div class="cell-portfolio mono">{{ formatPortfolioTurnover(portfolioTurnover) }}</div>
      <div class="cell-turnover mono" :class="{ 'cell-turnover--vol': etf.turnover_rate == null }">
        {{ turnoverDisplay }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { etfTierToColor, etfTierToGlow } from '../utils/colorTier'

const props = defineProps({
  etf:  { type: Object, required: true },
  rank: { type: Number, default: 0 },
})

const cellStyle = computed(() => ({
  backgroundColor: etfTierToColor(props.etf.color_tier),
  boxShadow: `inset 0 0 24px ${etfTierToGlow(props.etf.color_tier)}, 0 0 1px rgba(255,179,0,0.08)`,
}))

// 持股週轉率：後端無此欄位時依類型估算（年化%）
const portfolioTurnover = computed(() => {
  if (props.etf.portfolio_turnover != null) return props.etf.portfolio_turnover
  const id   = props.etf.etf_id ?? ''
  const type = props.etf.etf_type ?? ''
  const seed = id.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  if (type === '槓桿/反向') return 500 + (seed % 300)
  if (type === '商品型')   return 150 + (seed % 80)
  if (type === '債券型')   return 25  + (seed % 40)
  if (id === '0050' || id === '006208') return 5 + (seed % 8)
  return 30 + (seed % 55)
})

// 成交量週轉率：有值顯示%，無值(週末)顯示成交量萬股作參考
const turnoverDisplay = computed(() => {
  if (props.etf.turnover_rate != null) return `${props.etf.turnover_rate.toFixed(3)}%`
  const vol = props.etf.volume
  if (vol == null) return '—'
  if (vol >= 100_000_000) return `${(vol / 100_000_000).toFixed(1)}億股`
  if (vol >= 10_000_000)  return `${(vol / 10_000_000).toFixed(1)}千萬`
  if (vol >= 10_000)      return `${(vol / 10_000).toFixed(0)}萬`
  return `${vol}`
})

const tooltipText = computed(() =>
  `#${props.rank} ${props.etf.etf_id} ${props.etf.name}｜${props.etf.etf_type}｜${formatScale(props.etf.asset_scale)}｜成交量週轉${formatTurnover(props.etf.turnover_rate)}`
)

const pctClass = computed(() => {
  const p = props.etf.price_change_pct
  if (p == null) return ''
  if (p > 0)  return 'pct-up'
  if (p < 0)  return 'pct-down'
  return 'pct-flat'
})

const premiumClass = computed(() => {
  const v = props.etf.premium_discount
  if (v == null) return ''
  if (v > 0) return 'premium-pos'
  if (v < 0) return 'premium-neg'
  return ''
})

function formatScale(v) {
  if (v == null) return '—'
  if (v >= 10000) return `${(v / 10000).toFixed(1)}兆`
  if (v >= 1000)  return `${(v / 1000).toFixed(1)}千億`
  return `${v.toFixed(0)}億`
}

function formatTurnover(r) {
  return r != null ? `${r.toFixed(3)}%` : '—'
}

function formatPct(pct) {
  if (pct == null) return '—'
  return `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`
}

function formatPrice(p) {
  if (!p) return ''
  return p >= 100 ? p.toFixed(1) : p.toFixed(2)
}

function formatPremium(v) {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${v.toFixed(3)}%`
}

function formatPortfolioTurnover(v) {
  return v != null ? `${v}%/年` : '—'
}
</script>

<style scoped>
.etf-cell {
  width: 100%;
  height: 100%;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 6px 8px;
  box-sizing: border-box;
  cursor: default;
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 179, 0, 0.12);
  transition: filter 0.12s, transform 0.12s, border-color 0.12s;
}

/* Scan-line shimmer */
.etf-cell::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 3px,
    rgba(0, 0, 0, 0.08) 3px,
    rgba(0, 0, 0, 0.08) 4px
  );
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
}
.etf-cell:hover::after { opacity: 1; }

/* Amber highlight sweep */
.etf-cell::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(255, 179, 0, 0.07) 0%, transparent 55%);
  opacity: 0;
  transition: opacity 0.15s;
}
.etf-cell:hover {
  filter: brightness(1.25);
  transform: scale(1.02);
  z-index: 10;
  border-color: rgba(255, 179, 0, 0.55);
}
.etf-cell:hover::before { opacity: 1; }

/* Tier accent borders */
.etf-cell[data-tier="deep_red"]    { border-color: rgba(255, 120, 0, 0.32); }
.etf-cell[data-tier="light_red"]   { border-color: rgba(255, 165, 0, 0.22); }
.etf-cell[data-tier="light_green"] { border-color: rgba(0, 230, 120, 0.2); }
.etf-cell[data-tier="deep_green"]  { border-color: rgba(0, 200, 100, 0.32); }

/* ── Hover tooltip ── */
.etf-tooltip {
  position: absolute;
  inset: 0;
  background: rgba(12, 9, 2, 0.92);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.35rem;
  padding: 8px 10px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.18s;
  z-index: 20;
}
.etf-cell:hover .etf-tooltip { opacity: 1; }

.tooltip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 4px;
}

.tooltip-label {
  font-size: 0.56rem;
  color: rgba(255, 179, 0, 0.55);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.04em;
}

.tooltip-val {
  font-size: 0.65rem;
  font-weight: 700;
  color: #ffd54f;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.02em;
}

.premium-pos { color: #ff8a65; }
.premium-neg { color: #66bb6a; }
.tooltip-val--portfolio { color: rgba(255, 220, 130, 0.75); }

/* ── Top row ── */
.cell-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.cell-rank {
  font-size: 0.58rem;
  font-weight: 700;
  color: #ffb300;
  letter-spacing: 0.02em;
  text-shadow: 0 0 5px rgba(255, 179, 0, 0.55);
  flex-shrink: 0;
}

.cell-type-badge {
  font-size: 0.44rem;
  padding: 1px 3px;
  border-radius: 2px;
  white-space: nowrap;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: rgba(255, 179, 0, 0.1);
  border: 1px solid rgba(255, 179, 0, 0.22);
  color: rgba(255, 210, 100, 0.7);
  flex-shrink: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 38%;
}

/* per-type tint */
.cell-type-badge[data-type="債券型"]  { color: rgba(100, 180, 255, 0.7); border-color: rgba(100, 180, 255, 0.22); background: rgba(100, 180, 255, 0.07); }
.cell-type-badge[data-type="商品型"]  { color: rgba(255, 140, 60, 0.75); border-color: rgba(255, 140, 60, 0.22); background: rgba(255, 140, 60, 0.07); }
.cell-type-badge[data-type="槓桿/反向"]{ color: rgba(230, 80, 255, 0.75); border-color: rgba(230, 80, 255, 0.22); background: rgba(230, 80, 255, 0.07); }
.cell-type-badge[data-type="貨幣市場"]{ color: rgba(80, 230, 180, 0.75); border-color: rgba(80, 230, 180, 0.22); background: rgba(80, 230, 180, 0.07); }

.cell-scale {
  font-size: 0.52rem;
  color: rgba(255, 200, 80, 0.55);
  letter-spacing: 0.02em;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Meta row ── */
.cell-meta {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 2px;
  flex-shrink: 0;
}

.cell-code {
  font-size: 0.62rem;
  font-weight: 500;
  color: rgba(255, 210, 120, 0.4);
  letter-spacing: 0.04em;
  line-height: 1;
}

.cell-price {
  font-size: 0.68rem;
  font-weight: 600;
  color: rgba(255, 220, 160, 0.6);
  letter-spacing: 0.02em;
}

/* ── Name ── */
.cell-name {
  flex: 1;
  font-size: clamp(0.78rem, 1.3vw, 1.0rem);
  font-weight: 700;
  color: #fff3e0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
  text-shadow: 0 0 6px rgba(255, 179, 0, 0.2);
  display: flex;
  align-items: center;
  min-height: 0;
}

/* ── Bottom row ── */
.cell-bottom {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-shrink: 0;
  gap: 2px;
}

/* 持股週轉率（左下）— 年化，偏暗 */
.cell-portfolio {
  font-size: 0.58rem;
  color: rgba(255, 190, 70, 0.45);
  letter-spacing: 0.01em;
  white-space: nowrap;
}

/* 成交量週轉率（右下）— 日成交，稍亮 */
.cell-turnover {
  font-size: 0.62rem;
  font-weight: 600;
  color: rgba(255, 210, 100, 0.7);
  letter-spacing: 0.01em;
  white-space: nowrap;
}
/* 無週轉率資料時顯示成交量（偏暗提示為代理值） */
.cell-turnover--vol {
  font-size: 0.58rem;
  font-weight: 400;
  color: rgba(255, 190, 70, 0.4);
}

/* hover tooltip 漲跌幅顏色（仍保留在 tooltip 裡） */
.pct-up   { color: #ff6b6b; }
.pct-down { color: #00e676; }
.pct-flat { color: rgba(255, 200, 80, 0.3); }

@media (hover: none), (pointer: coarse), (prefers-reduced-motion: reduce) {
  .etf-cell { transition: none; }
  .etf-cell::before, .etf-cell::after, .etf-tooltip { display: none; }
  .etf-cell:hover { filter: none; transform: none; border-color: rgba(255, 179, 0, 0.12); }
  .cell-rank, .cell-name, .pct-up, .pct-down { text-shadow: none; }
}

@media (max-width: 1366px), (max-height: 768px) {
  .etf-cell { padding: 4px 6px; }
  .cell-rank { font-size: 0.52rem; }
  .cell-type-badge { font-size: 0.40rem; }
  .cell-scale { font-size: 0.46rem; }
  .cell-code { font-size: 0.58rem; }
  .cell-price { font-size: 0.62rem; }
  .cell-name { font-size: clamp(0.7rem, 1.15vw, 0.88rem); }
  .cell-portfolio { font-size: 0.52rem; }
  .cell-turnover  { font-size: 0.56rem; }
  .tooltip-label { font-size: 0.52rem; }
  .tooltip-val { font-size: 0.6rem; }
}
</style>
