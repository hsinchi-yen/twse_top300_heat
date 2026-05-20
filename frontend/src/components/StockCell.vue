<template>
  <div
    class="stock-cell"
    :class="{ 'cell-highlighted': highlighted }"
    :data-tier="stock.color_tier"
    :style="cellStyle"
    :title="`#${stock.rank} ${stock.stock_id} ${stock.name}｜${stock.sector}｜${valueLabel}`"
  >
    <!-- 頂部：排名 + 題材 -->
    <div class="cell-top">
      <span class="cell-rank mono">#{{ stock.rank }}</span>
      <span class="cell-sector">{{ stock.sector }}</span>
    </div>

    <!-- 代號 + 現價 / 收盤價 -->
    <div class="cell-meta">
      <span class="cell-code mono">{{ stock.stock_id }}</span>
      <span class="cell-price mono" v-if="stock.close_price">{{ formatPrice(stock.close_price) }}</span>
    </div>

    <!-- 名稱 + 買入評分 -->
    <div class="cell-name">
      <span class="cell-name-text">{{ stock.name }}</span>
      <span v-if="scoreLabel !== null" class="cell-score mono"> - {{ scoreLabel }}</span>
    </div>

    <!-- 底部：數值 + 漲跌幅 -->
    <div class="cell-bottom">
      <div class="cell-value mono">{{ valueLabel }}</div>
      <div class="cell-pct mono" :class="pctClass">{{ formatPct(stock.price_change_pct) }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { tierToColor, tierToGlow } from '../utils/colorTier'

const props = defineProps({
  stock:        { type: Object,  required: true },
  mode:         { type: String,  default: 'turnover' },
  highlighted:  { type: Boolean, default: false },
  buyScore:       { type: Object,  default: null },
  scoresLoaded:   { type: Boolean, default: false },
  scoresFetching: { type: Boolean, default: false },
})

const cellStyle = computed(() => {
  const tier = props.stock.color_tier
  if (props.highlighted) {
    return {
      backgroundColor: tierToColor(tier),
      boxShadow: `inset 0 0 24px ${tierToGlow(tier)}, 0 0 28px 8px rgba(0, 229, 255, 0.8)`,
      borderColor: '#00e5ff',
    }
  }
  return {
    backgroundColor: tierToColor(tier),
    boxShadow: `inset 0 0 24px ${tierToGlow(tier)}, 0 0 1px rgba(0,229,255,0.08)`,
  }
})

const valueLabel = computed(() => {
  if (props.mode === 'turnover') {
    const r = props.stock.turnover_rate
    return r != null ? `${r.toFixed(2)}%` : '—'
  }
  const v = props.stock.volume
  if (v == null) return '—'
  const zhang = Math.round(v / 1000)
  return zhang >= 10000
    ? `${(zhang / 10000).toFixed(1)}萬`
    : zhang >= 1000
      ? `${(zhang / 1000).toFixed(1)}K`
      : `${zhang}張`
})

// null    → never requested scores (show nothing)
// '...'   → fetch in progress, this stock not yet scored
// 'N/A'   → fetch complete, no score available for this stock
// '18/24' → scored
const scoreLabel = computed(() => {
  if (!props.scoresLoaded) {
    return props.scoresFetching ? '...' : null
  }
  const s = props.buyScore
  if (!s || s.score == null) {
    return props.scoresFetching ? '...' : 'N/A'
  }
  return `${s.score}/${s.max_score ?? 24}`
})

const pctClass = computed(() => {
  const p = props.stock.price_change_pct
  if (p == null) return ''
  if (p > 0)  return 'pct-up'
  if (p < 0)  return 'pct-down'
  return 'pct-flat'
})

function formatPct(pct) {
  if (pct == null) return '—'
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function formatPrice(p) {
  if (p == null || p === 0) return ''
  return p >= 100 ? p.toFixed(1) : p.toFixed(2)
}
</script>

<style scoped>
.stock-cell {
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
  border: 1px solid rgba(0, 229, 255, 0.1);
  transition: filter 0.12s, transform 0.12s, border-color 0.12s;
}

/* Scan-line shimmer on hover */
.stock-cell::after {
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
/* Hover shimmer reveal */
.stock-cell:hover::after { opacity: 1; }

/* Top-left highlight sweep on hover */
.stock-cell::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(0, 229, 255, 0.07) 0%, transparent 55%);
  opacity: 0;
  transition: opacity 0.15s;
}
.stock-cell:hover {
  filter: brightness(1.25);
  transform: scale(1.02);
  z-index: 10;
  border-color: rgba(0, 229, 255, 0.5);
}
.stock-cell:hover::before { opacity: 1; }

/* ── tier accent borders ── */
.stock-cell[data-tier="deep_red"]    { border-color: rgba(255, 60,  60,  0.3); }
.stock-cell[data-tier="light_red"]   { border-color: rgba(255, 100, 100, 0.2); }
.stock-cell[data-tier="light_green"] { border-color: rgba(0,   230, 120, 0.2); }
.stock-cell[data-tier="deep_green"]  { border-color: rgba(0,   200, 100, 0.3); }

/* ── 頂部列 ── */
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
  color: #00e5ff;
  letter-spacing: 0.02em;
  text-shadow: 0 0 5px rgba(0, 229, 255, 0.55);
}

.cell-sector {
  font-size: 0.5rem;
  color: rgba(180, 220, 255, 0.45);
  background: rgba(0, 229, 255, 0.06);
  border: 1px solid rgba(0, 229, 255, 0.1);
  padding: 1px 3px;
  border-radius: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 56%;
  flex-shrink: 1;
}

/* ── 代號列：代號 + 現價 ── */
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
  color: rgba(160, 210, 240, 0.45);
  letter-spacing: 0.04em;
  line-height: 1;
}

.cell-price {
  font-size: 0.68rem;
  font-weight: 600;
  color: rgba(200, 230, 255, 0.6);
  letter-spacing: 0.02em;
}

/* ── 名稱 + 評分 ── */
.cell-name {
  flex: 1;
  font-size: clamp(0.82rem, 1.4vw, 1.05rem);
  font-weight: 700;
  color: #e8f4ff;
  line-height: 1.2;
  text-shadow: 0 0 6px rgba(200, 230, 255, 0.25);
  display: flex;
  align-items: center;
  min-height: 0;
  overflow: hidden;
}

.cell-name-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 1;
  min-width: 0;
}

.cell-score {
  font-size: 0.58rem;
  font-weight: 400;
  color: rgba(140, 200, 230, 0.55);
  white-space: nowrap;
  flex-shrink: 0;
  letter-spacing: 0.01em;
}

/* ── 底部：數值 + 漲跌幅 ── */
.cell-bottom {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-shrink: 0;
  gap: 2px;
}

.cell-value {
  font-size: 0.62rem;
  color: rgba(140, 200, 230, 0.6);
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.cell-pct {
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
}
.pct-up   { color: #ff6b6b; text-shadow: 0 0 7px rgba(255, 80, 80, 0.55); }
.pct-down { color: #00e676; text-shadow: 0 0 7px rgba(0, 230, 120, 0.55); }
.pct-flat { color: rgba(140, 200, 230, 0.35); }

.cell-highlighted {
  animation: pulse-highlight 0.6s ease-in-out 3;
  z-index: 20;
}

@keyframes pulse-highlight {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.45; }
}

@media (hover: none), (pointer: coarse), (prefers-reduced-motion: reduce) {
  .stock-cell {
    transition: none;
  }

  .stock-cell::before,
  .stock-cell::after {
    display: none;
  }

  .stock-cell:hover {
    filter: none;
    transform: none;
    border-color: rgba(0, 229, 255, 0.1);
  }

  .cell-rank,
  .cell-name,
  .pct-up,
  .pct-down {
    text-shadow: none;
  }
}

@media (max-width: 1366px), (max-height: 768px) {
  .stock-cell {
    padding: 4px 6px;
  }

  .cell-rank {
    font-size: 0.52rem;
  }

  .cell-sector {
    font-size: 0.46rem;
    max-width: 52%;
  }

  .cell-code {
    font-size: 0.58rem;
  }

  .cell-price {
    font-size: 0.62rem;
  }

  .cell-name {
    font-size: clamp(0.74rem, 1.2vw, 0.9rem);
  }

  .cell-score {
    font-size: 0.52rem;
  }

  .cell-value {
    font-size: 0.56rem;
  }

  .cell-pct {
    font-size: 0.66rem;
  }
}
</style>
