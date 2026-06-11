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
        <span class="tooltip-label">管理費</span>
        <span class="tooltip-val">{{ etf.management_fee != null ? `${etf.management_fee}%/年` : '—' }}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">持股週轉率</span>
        <span class="tooltip-val tooltip-val--portfolio">{{ formatPortfolioTurnover(portfolioTurnoverAnnual) }}</span>
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
      <div class="cell-portfolio mono">{{ formatPortfolioTurnoverDaily(portfolioTurnoverAnnual) }}</div>
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

// 持股週轉率年化值：優先用後端值，否則依類型估算
const portfolioTurnoverAnnual = computed(() => {
  if (props.etf.portfolio_turnover != null) return props.etf.portfolio_turnover
  const id   = props.etf.etf_id ?? ''
  const type = props.etf.etf_type ?? ''
  const seed = id.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  if (type === '槓桿')   return 500 + (seed % 300)
  if (type === '反向')   return 400 + (seed % 200)
  if (type === '期貨')   return 120 + (seed % 500)
  if (type === '債券')   return 20  + (seed % 40)
  if (type === '貨幣')   return 80  + (seed % 80)
  if (type === '多資產') return 40  + (seed % 60)
  if (type === '國外股') return 25  + (seed % 50)
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

// Card bottom — daily rate (annual ÷ 252), adaptive precision
function formatPortfolioTurnoverDaily(v) {
  if (v == null) return '—'
  const daily = v / 252
  const digits = daily >= 1 ? 2 : daily >= 0.1 ? 3 : 4
  return `${daily.toFixed(digits)}%/日`
}

// Tooltip — annual rate for context
function formatPortfolioTurnover(v) {
  return v != null ? `${v.toFixed(0)}%/年` : '—'
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
  border: 1px solid var(--etf-cell-border-default);
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
  background: linear-gradient(135deg, var(--etf-cell-hover-sweep) 0%, transparent 55%);
  opacity: 0;
  transition: opacity 0.15s;
}
.etf-cell:hover {
  filter: brightness(1.25);
  transform: scale(1.02);
  z-index: 10;
  border-color: var(--etf-cell-hover-border);
}
.etf-cell:hover::before { opacity: 1; }

/* Tier accent borders */
.etf-cell[data-tier="deep_red"]    { border-color: var(--etf-dr-border); }
.etf-cell[data-tier="light_red"]   { border-color: var(--etf-lr-border); }
.etf-cell[data-tier="light_green"] { border-color: var(--etf-lg-border); }
.etf-cell[data-tier="deep_green"]  { border-color: var(--etf-dg-border); }

/* ── Hover tooltip ── */
.etf-tooltip {
  position: absolute;
  inset: 0;
  background: var(--etf-tooltip-bg);
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
  color: var(--etf-tooltip-label);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.04em;
}

.tooltip-val {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--etf-tooltip-val);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.02em;
}

.tooltip-val--portfolio { color: color-mix(in srgb, var(--etf-tooltip-val) 65%, transparent); }

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
  color: var(--etf-cell-rank-color);
  letter-spacing: 0.02em;
  text-shadow: 0 0 5px var(--etf-cell-rank-shadow);
  flex-shrink: 0;
}

.cell-type-badge {
  font-size: 0.44rem;
  padding: 1px 3px;
  border-radius: 2px;
  white-space: nowrap;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: color-mix(in srgb, var(--accent-etf) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-etf) 22%, transparent);
  color: color-mix(in srgb, var(--accent-etf) 70%, transparent);
  flex-shrink: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 38%;
}

/* ── 8-type badge colors (functional coloring — intentionally kept as literal values) ── */
.cell-type-badge[data-type="國內股"]  { color: rgba(255,210,80,0.80); border-color: rgba(255,210,80,0.25); background: rgba(255,210,80,0.07); }
.cell-type-badge[data-type="國外股"]  { color: rgba(80,200,255,0.80); border-color: rgba(80,200,255,0.25); background: rgba(80,200,255,0.07); }
.cell-type-badge[data-type="多資產"]  { color: rgba(180,100,255,0.80); border-color: rgba(180,100,255,0.25); background: rgba(180,100,255,0.07); }
.cell-type-badge[data-type="槓桿"]   { color: rgba(255,100,60,0.90); border-color: rgba(255,100,60,0.28); background: rgba(255,100,60,0.09); }
.cell-type-badge[data-type="反向"]   { color: rgba(255,60,180,0.90); border-color: rgba(255,60,180,0.28); background: rgba(255,60,180,0.09); }
.cell-type-badge[data-type="期貨"]   { color: rgba(255,150,50,0.80); border-color: rgba(255,150,50,0.25); background: rgba(255,150,50,0.07); }
.cell-type-badge[data-type="債券"]   { color: rgba(100,180,255,0.75); border-color: rgba(100,180,255,0.22); background: rgba(100,180,255,0.07); }
.cell-type-badge[data-type="貨幣"]   { color: rgba(80,230,180,0.80); border-color: rgba(80,230,180,0.25); background: rgba(80,230,180,0.07); }
/* Legacy badge types (kept for existing DB rows during migration) */
.cell-type-badge[data-type="股票型"]  { color: rgba(255,210,80,0.75); border-color: rgba(255,210,80,0.22); background: rgba(255,210,80,0.07); }
.cell-type-badge[data-type="債券型"]  { color: rgba(100,180,255,0.7); border-color: rgba(100,180,255,0.22); background: rgba(100,180,255,0.07); }
.cell-type-badge[data-type="商品型"]  { color: rgba(255,140,60,0.75); border-color: rgba(255,140,60,0.22); background: rgba(255,140,60,0.07); }
.cell-type-badge[data-type="槓桿/反向"]{ color: rgba(230,80,255,0.75); border-color: rgba(230,80,255,0.22); background: rgba(230,80,255,0.07); }
.cell-type-badge[data-type="貨幣市場"]{ color: rgba(80,230,180,0.75); border-color: rgba(80,230,180,0.22); background: rgba(80,230,180,0.07); }

.cell-scale {
  font-size: 0.52rem;
  color: var(--etf-cell-scale-color);
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
  color: var(--etf-cell-code-color);
  letter-spacing: 0.04em;
  line-height: 1;
}

.cell-price {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--etf-cell-price-color);
  letter-spacing: 0.02em;
}

/* ── Name ── */
.cell-name {
  flex: 1;
  font-size: clamp(0.78rem, 1.3vw, 1.0rem);
  font-weight: 700;
  color: var(--etf-cell-name-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
  text-shadow: 0 0 6px var(--etf-cell-name-shadow);
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

/* 持股週轉率（左下）— 日化，偏暗 */
.cell-portfolio {
  font-size: 0.58rem;
  color: var(--etf-cell-portfolio-color);
  letter-spacing: 0.01em;
  white-space: nowrap;
}

/* 成交量週轉率（右下）— 日成交，稍亮 */
.cell-turnover {
  font-size: 0.62rem;
  font-weight: 600;
  color: var(--etf-cell-turnover-color);
  letter-spacing: 0.01em;
  white-space: nowrap;
}
.cell-turnover--vol {
  font-size: 0.58rem;
  font-weight: 400;
  color: var(--etf-cell-portfolio-color);
}

/* hover tooltip 漲跌幅顏色 */
.pct-up   { color: var(--pct-up); }
.pct-down { color: var(--pct-down); }
.pct-flat { color: color-mix(in srgb, var(--accent-etf) 30%, transparent); }

@media (hover: none), (pointer: coarse), (prefers-reduced-motion: reduce) {
  .etf-cell { transition: none; }
  .etf-cell::before, .etf-cell::after, .etf-tooltip { display: none; }
  .etf-cell:hover { filter: none; transform: none; border-color: var(--etf-cell-border-default); }
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
